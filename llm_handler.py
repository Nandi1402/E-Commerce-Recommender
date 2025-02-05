from enum import Enum
import logging

from google.cloud import storage

import vertexai
from vertexai.generative_models import GenerativeModel

from utils.rag_constants import PROJECT_ID, GEMINI_MODEL_REGION, GEMINI_MODEL, FLANT5_MODEL_REGION
from utils.rag_constants import Mode, MODEL_MODE
from utils.rag_constants import LLAMA_API_KEY, LLAMA_ENDPOINT
from utils.neo4j_client import get_driver,exec_query, nodes_to_dict, records_to_dict, KnowledgeGraphLoader
from utils.llama_client import LLAMAClient
from utils.neo4j_query_templates import PROMPT_CYPHER_READ, PROMPT_TEMPLATE_NO_AUGMENTATION, FINAL_PROMPT_TEMPLATE

from flask_graph_visualization import get_categories

class AvailableLLMs(Enum):
    GEMINI = 'Gemini',
    LLAMA = "llama3.1-70b"

class LLMHandler:
    """
    Usage:

    from llm_handler import LLMHandler, AvailableLLMs

    llm_handler = LLMHandler(AvailableLLMs.GEMINI)
    llm_handler.get_llm_response(user_query)
    """

    retrieved_neo4j_records = []

    def __init__(self, selected_model):
        self.MAX_TOKEN_SIZE = 512 # default

        if selected_model == AvailableLLMs.GEMINI:
            vertexai.init(project=PROJECT_ID, location=GEMINI_MODEL_REGION)
            self.model = GenerativeModel(GEMINI_MODEL)
            self.MAX_TOKEN_SIZE = 1000000 # 1 million
        elif selected_model == AvailableLLMs.LLAMA:
            vertexai.init(project=PROJECT_ID, location=FLANT5_MODEL_REGION)
            self.model = LLAMAClient()
            self.MAX_TOKEN_SIZE = 128000 # 120 thousand

        self.neo4j_driver = get_driver()

        # get the current state of the knowledge graph
        self.main_categories, self.categories, self.main_category_counts, self.category_counts = get_categories(self.neo4j_driver)

    def download_from_gcs(self,bucket_name, source_blob_name, destination_file_name):
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(source_blob_name)
        blob.download_to_filename(destination_file_name)
    
    def prompt_llm(self,prompt):
        response = self.model.generate_content(prompt)
        return self._get_text_from_model_response(response)
    
    def get_llm_response(self, user_query):
        """
        Returns:
            llm_recommendation: the LLM's recommendation
            selected_nodes: a list of Neo4j Nodes

        Example query:
        "What's a good name for a flower shop that specializes in selling bouquets of dried flowers?"
        """
        model_response = ''
        cypher_query = ''
        if MODEL_MODE == Mode.Graph:
            augmented_query, cypher_query = self._augment_from_graph(user_query)
        elif MODEL_MODE == Mode.Vector:
            augmented_query = self._augment_from_vector(user_query)

        try:
            model_response = self.model.generate_content(augmented_query)
            logging.info(f"Final query: {augmented_query[:5000]}\nModel response: {model_response}")
        except Exception as e:
            logging.info(f"Error generating content: {e}")
        finally:
            return LLMResponse(self.neo4j_driver, model_response, self.retrieved_neo4j_records, cypher_query)

    def _augment_from_graph(self, user_query):
        # default non-augmented query
        # we replace this with an augmented query in the next step
        cypher_query = ''
        augmented_query = PROMPT_TEMPLATE_NO_AUGMENTATION.format(
            user_query=user_query
        )

        try:
            # Retrieve related information from Neo4J
            # Use the LLM to generate a Cypher query for us
            prompt_for_cypher = PROMPT_CYPHER_READ.format(
                main_categories=self.main_categories,
                categories=self.categories,
                user_query=user_query
                )
            logging.info(f"LLM Prompt to generate Cypher query: {prompt_for_cypher}")
            print(prompt_for_cypher)
            generated_cypher = self.model.generate_content(prompt_for_cypher)

            # Extract just the Cypher query from between the ```cypher and ``` markers
            cypher_query = self._get_text_from_generated_cypher(generated_cypher)                      

            self.retrieved_neo4j_records = exec_query(
                self.neo4j_driver,
                cypher_query
            )

            # node properties to pass to the LLM as context
            condensed_graph_nodes = records_to_dict(
                self.retrieved_neo4j_records
                , ["element_id", "store", "description", "average_rating", "categories"])

            # Add the retrieved results to the prompt
            augmented_query = FINAL_PROMPT_TEMPLATE.format(
                user_query=user_query,
                response=condensed_graph_nodes
            )
            logging.info(f"LLM Prompt to generate recommendations: {augmented_query}")
            print(augmented_query)

            # trunctae content to the maxmimum allowed by the model if it's oversized
            if len(augmented_query) >= self.MAX_TOKEN_SIZE:
                augmented_query = augmented_query[:self.MAX_TOKEN_SIZE]
        except Exception as e:
            logging.error(f"Could not retrieve related information from Neo4J: {e}")
            self.retrieved_neo4j_records = []
            
        return augmented_query, cypher_query

    def _augment_from_vector(self,user_query):
        # unimplemented
        return user_query

    def _get_text_from_generated_cypher(self, response):
        cypher_text = self._get_text_from_model_response(response)
        if 'cypher' in cypher_text:
            extracted_query = cypher_text.split('```cypher\n')[1].split('\n```')[0]
        else:
            extracted_query = cypher_text
        return extracted_query

    def _get_text_from_model_response(self, response):
        if type(response) == vertexai.generative_models.GenerationResponse:
            return response.text
        elif 'text' in response:
            return response['text']
        else:
            return response

class LLMResponse:
    def __init__(self, neo4j_driver, model_response, retrieved_neo4j_records , cypher_query=''):
        self.neo4j_driver = neo4j_driver
        self.cypher_query = cypher_query
        self.text, self.graph_nodes = self._split_response_and_selected_nodes(model_response, retrieved_neo4j_records)
        self.graph_nodes_dict = nodes_to_dict(
          graph_nodes = self.graph_nodes
        , node_properties = ["element_id", "title", "description", "images"]
        )

        # post-process images to JSON format
        for ele in self.graph_nodes_dict:
            imgs = ele.get("images")
            if imgs:
                imgs.replace("(","[").replace(")","]")
                ele["images"] = imgs
    
    def _split_response_and_selected_nodes(self, llm_response, retrieved_neo4j_records):
        """
        This function parses the raw llm response and formats it so it can be passed to the frontend.

        Parameters:
            llm_response: expected to be a recommendation followed by the string "element_ids: " and a list of Neo4j Node element_ids
            retrieved_neo4j_records: the raw response retrieved from Neo4J

        Returns:
            recommendation_only: the LLM's recommendation with the node element_ids removed
            selected_nodes: a list of Neo4j Nodes
        
        Example usage:

        retrieved_nodes = llm_handler.retrieved_neo4j_records
        llm_recommendation, selected_nodes = _get_selected_nodes(llm_response, retrieved_nodes)
        for n in selected_nodes:
            print(n['title'])
            print(n['images'])
        """
        if type(llm_response) == vertexai.generative_models.GenerationResponse:
            response = llm_response.text
        else:
            response = llm_response
        
        split_response = response.split("element_ids: ")
        if len(split_response) == 1:
            return response, []
        recommendation_only = split_response[0]
        ids_only = split_response[1]

        # extract neo4j node element_ids from the llm_response
        element_ids = []
        ids = ids_only.split(',')
        for id in ids:
            element_ids.append(id.strip())

        selected_nodes = []
        # get the selected nodes from the retrieved_neo4j_records
        for element_id in element_ids:
            for record in retrieved_neo4j_records:
                node = record[0]
                if node.element_id == element_id:
                    selected_nodes.append(node)

        if not self._nodes_have_data(selected_nodes):
            selected_nodes = self._get_node_data_from_neo4j(selected_nodes)

        # return recommendation_only first to match with get_llm_response's return order
        return recommendation_only, selected_nodes

    def _nodes_have_data(self, node_subset):
        """
        Check if the retrieved nodes have all the data we need for the frontend.
        """
        for node in node_subset:
            if node["title"] == "" or node["description"] == "" or node["images"] == "":
                return False
        return True
    
    def _get_node_data_from_neo4j(self, selected_nodes):
        element_ids = [node.element_id for node in selected_nodes]
        return exec_query(self.neo4j_driver, 
                   "MATCH (n) WHERE n.element_id IN $element_ids RETURN n",
                   {"element_ids": element_ids}
                   )