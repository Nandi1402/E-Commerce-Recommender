"""
Author: Sally

class GirvanNewman

Operates on a neo4j graph.
To set up the noe4j graph, run:
    ONTOLOGY = "e_commerce_website_pooja.owl"
    CSV_DATA = "giftcard.csv"
    kg_loader = neo4j_client.KnowledgeGraphLoader(ONTOLOGY, CSV_DATA)
    kg_loader.load_knowledge_graph(reset = True)

Usage:
    from girvan_newman import GirvanNewman

    k = 100
    gn = GirvanNewman(iteration=k)
    gn.draw_colored_graph(iteration=k)
    gn.draw_gn_dendrogram()
"""

import networkx as nx
import itertools
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import pdist, squareform

from utils import neo4j_client, print_debug

FETCH_NEO4J_GRAPH = """
MATCH (n)
OPTIONAL MATCH (n)-[r]-() 
RETURN *
"""

"""
MATCH (n)-[r]->(c) RETURN *
"""

class GirvanNewman():

    def __init__(self):
        with neo4j_client.get_driver() as driver:
            self.nx_graph, self.communities = self.run_girvan_newman(driver)
        print("Finished running Girvan-Newman.")

    def run_girvan_newman(self, driver):
        print("Running Girvan-Newman algorithm... This may take a while.")
        # run Girvan-Newman algorithm
        # NetworkX girvan_newman documentation: https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.community.centrality.girvan_newman.html
        # gn_comm: Each set of node is a community, 
        #          each tuple is a sequence of communities at a particular level of the algorithm.
        nx_graph = self._build_networkx_graph(driver)
        nx_graph_undirected = nx_graph.to_undirected() # not implemented for directed graphs
        girvan_newman_results = nx.community.girvan_newman(nx_graph_undirected)
        return nx_graph_undirected, list(girvan_newman_results)

    def draw_colored_graph(self, iteration=100):
        """
        Colors the nodes of the NetworkX graph (G) according to the results of a neo4j query (query_results)
        https://stackoverflow.com/a/74578385

        See also:
          * The documentation for nx.draw: https://networkx.org/documentation/stable/reference/generated/networkx.drawing.nx_pylab.draw.html
          * See the documentation for networkx.draw_networkx, section on node_color: https://networkx.org/documentation/stable/reference/generated/networkx.drawing.nx_pylab.draw_networkx.html#networkx.drawing.nx_pylab.draw_networkx
        """
        G = self.nx_graph
        colormap = self._make_gn_colormap(iteration)

        nx.draw(G, with_labels=False, node_color=colormap, node_size=20, font_color='black')

    def draw_gn_dendrogram(self):
        """
        communities: expects a list of the Generator returned by NetworkX's girvan_newman function.
        i.e., list(girvan_newman_results)
        """
        communities = self.communities
        
        # Use community size to determine linkage order
        community_sizes = [len(comm) for comm in communities]

        # Calculate distances between communities
        dist_matrix = pdist(np.array(community_sizes).reshape(-1, 1), metric='euclidean')

        # Create linkage matrix
        Z = linkage(dist_matrix, method='average')
        
        # Plot the dendrogram
        plt.figure(figsize=(15, 6))
        dendrogram(Z, labels=[f'{i+1}' for i in range(len(communities))])
        plt.title('Dendrogram of Communities from Girvan-Newman Algorithm')
        plt.xlabel('Communities')
        plt.ylabel('Distance')
        plt.show()

    def _build_networkx_graph(self, driver):
        """
        Convert a neo4j graph into a networkX graph
        source: https://stackoverflow.com/a/63658690
        
        :param driver: the Neo4j driver.
        """
        G = nx.Graph() # initialize empty NetworkX graph
        
        driver.verify_connectivity()
        results = driver.session().run(FETCH_NEO4J_GRAPH)
        
        G = nx.MultiDiGraph()
        
        nodes = list(results.graph()._nodes.values())
        for node in nodes:
            G.add_node(node.element_id, labels=node._labels, properties=node._properties)
        
        rels = list(results.graph()._relationships.values())
        for rel in rels:
            G.add_edge(rel.start_node.element_id
                       , rel.end_node.element_id
                       , key=rel.element_id
                       , type=rel.type
                       , properties=rel._properties)

        return G

    def _make_gn_colormap(self, k):
        """
        k: the kth iteration

        Creates a colormap that maps colors to each node according to its community.
        
        Standardizes the results of nx.community.girvan_newman() for my draw_colored_graph function
        girvan_newman_results is assumed to be a series of arrays e.g.
        (
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 25, 64, 100, 101, 102, 103, 104, 105, 106, 107, 108, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 152, 153, 154]
          , [15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 109, 110, 111, 112, 113, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168]
          , [169, 170]
        ) where the first array contains the nodes belonging to Community 1, the second array those belonging to Community 2, and so on.
        For more on girvan_newman_reults's format, see NetworkX girvan_newman documentation: https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.community.centrality.girvan_newman.html
        """
        communities = self.communities

        cluster_k = communities[k] # iteration k
        
        mpl_colormap = plt.get_cmap('viridis')
        colormap = {}

        comm_id = 0
        num_comms = len(cluster_k)
        colors = mpl_colormap(np.linspace(0, 1, num_comms))
        for community in cluster_k:
            print_debug(f"iter:{k}, comm_id: {comm_id}, comm:{community}")
            for node_id in community:
                colormap[node_id] = matplotlib.colors.rgb2hex(colors[comm_id])
            comm_id = comm_id + 1
            
        # convert the colormap from a map to a simple array of colors
        dict(sorted(colormap.items()))
        colormap = list(colormap.values())

        print_debug(f"\ncolormap:{colormap}")
        
        return colormap

    