import logging
from flask import Blueprint,Flask, render_template, jsonify, request
from utils.rag_constants import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
from utils.neo4j_client import get_driver, exec_query

# Create blueprint
graph = Blueprint('graph', __name__, 
                 template_folder='templates',
                 static_folder='static',
                 url_prefix='/graph')

try:
    # Test the connection
    driver = get_driver()
    driver.verify_connectivity()
except Exception as e:
    logging.error(f"Failed to connect to Neo4j: {str(e)}. Please check if the Neo4j server is on and that the connection credentials are correctly set in utils/rag_constants.py")
    driver = None

def get_categories(driver=driver):
    """
    Returns main categories, categories, main category counts, and category counts
    """
    if not driver:
        return [], [], {}, {}
    
    try:
        # Query for mainCategory counts
        main_cat_query = """
        MATCH (n)
        WHERE n.main_category IS NOT NULL
        WITH n.main_category as category, count(n) as count
        RETURN collect({category: category, count: count}) as counts
        """
            
        # Query for category counts (needs to handle comma-separated values)
        cat_query = """
        MATCH (n)
        WHERE n.categories IS NOT NULL
        UNWIND split(n.categories, ',') as category
        WITH trim(category) as trimmed_category
        WHERE trimmed_category <> ''
        WITH trimmed_category, count(*) as count
        RETURN collect({category: trimmed_category, count: count}) as counts
        """
            
        # Get categories and their counts
        main_result = exec_query(driver, main_cat_query)[0]
        cat_result = exec_query(driver, cat_query)[0]
            
        # Process mainCategories
        main_cats = []
        main_cat_counts = {}
        for item in main_result['counts']:
            cat = item['category'].strip("'").strip('"').strip()
            if cat:
                main_cats.append(cat)
                main_cat_counts[cat] = item['count']
            
        # Process categories
        cats = []
        cat_counts = {}
        for item in cat_result['counts']:
            cat = item['category'].strip("'").strip('"').strip()
            if cat:
                cats.append(cat)
                cat_counts[cat] = item['count']
            
        # Sort categories case-insensitive
        main_cats = sorted(set(main_cats), key=str.casefold)
        cats = sorted(set(cats), key=str.casefold)
            
        return main_cats, cats, main_cat_counts, cat_counts
    except Exception as e:
        logging.error(f"Error getting categories: {str(e)}")
        return [], [], {}, {}

def get_filtered_graph_data(main_categories=None, categories=None):
    if not driver:
        return [], []
    
    try:
        conditions = []
        if main_categories:
            conditions.append("n.main_category IN $main_categories")
        if categories:
            # Modified to check if any of the categories exist in the comma-separated string
            categories_condition = " OR ".join([
                "any(cat in split(n.categories, ',') WHERE trim(cat) = $cat)" 
                for cat in categories
            ])
            if categories_condition:
                conditions.append(f"({categories_condition})")
        
        where_clause = " OR ".join(conditions) if conditions else "false" # don't show if no filters
        
        query = f"""
        MATCH (n)-[r]->(m)
        WHERE {where_clause}
        RETURN collect(distinct {{
            id: elementId(n), 
            label: labels(n)[0], 
            properties: properties(n)
        }}) as nodes,
                collect(distinct {{
                    from: elementId(n), 
                    to: elementId(m), 
                    type: type(r)
                }}) as relationships
        """
        
        params = {
            "main_categories": main_categories or [],
            "cat": categories[0] if categories else None  # We'll use this in the UNWIND
        }
        
        result = exec_query(driver, query, params)[0]
        return result['nodes'], result['relationships']
    except Exception as e:
        logging.error(f"Error querying Neo4j: {str(e)}")
        return [], []


# Change route to blueprint route
@graph.route('/')
def visualization():
    return render_template('graph.html')

@graph.route('/get_categories')
def get_categories_ajax():
    main_categories, categories, main_cat_counts, cat_counts = get_categories()
    return jsonify({
        'main_categories': main_categories or [],
        'categories': categories or [],
        'main_category_counts': main_cat_counts or [],
        'category_counts': cat_counts or []
    })

@graph.route('/graph-data')
def get_graph():
    try:
        main_cats = request.args.getlist('main_categories')
        cats = request.args.getlist('category')
        
        nodes, relationships = get_filtered_graph_data(
            main_categories=main_cats if main_cats else None,
            categories=cats if cats else None
        )
        return jsonify({"nodes": nodes, "edges": relationships})
    except Exception as e:
        logging.error(f"Error in get_graph: {str(e)}")
        return jsonify({"error": str(e)}), 500

@graph.route('/update-category-counts')
def update_category_counts():
    try:
        selected_main_categories = request.args.getlist('main_categories')
        
        # if no categories are selected, return empty result
        if not selected_main_categories:
            return jsonify({'category_counts': {}})
            
        driver = get_driver()
        query = """
        MATCH (n)-[]->(m)
        WHERE n.main_category IN $main_categories
        AND n.categories IS NOT NULL
        UNWIND split(n.categories, ',') as category
        WITH trim(category) as temp_category, m
        WITH CASE 
            WHEN temp_category STARTS WITH "'" AND temp_category ENDS WITH "'" 
            THEN substring(temp_category, 1, size(temp_category)-2)
            WHEN temp_category STARTS WITH "'" 
            THEN substring(temp_category, 1)
            WHEN temp_category ENDS WITH "'" 
            THEN substring(temp_category, 0, size(temp_category)-1)
            ELSE temp_category 
        END as trimmed_category, m
        WHERE trimmed_category <> ''
        RETURN trimmed_category as category, COUNT(DISTINCT m) as count
        """
        results = exec_query(driver, query, parameters={"main_categories": selected_main_categories})
        
        category_counts = {record['category']: record['count'] for record in results}
        return jsonify({'category_counts': category_counts})
    except Exception as e:
        logging.error(f"Error in update_category_counts: {str(e)}")
        return jsonify({"error": str(e)}), 500