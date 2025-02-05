"""
Author: Pooja
"""

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
import json
import os
import re
import csv
from datetime import datetime
import logging

from utils.rag_constants import *

# Set up logging
logging.basicConfig(level=logging.INFO)

class OntologyProcessor:

    # Set up pipeline options for running on Dataflow
    pipeline_options = PipelineOptions(
        runner='DataflowRunner',
        project=PROJECT_ID,
        region=REGION,
        temp_location=f'gs://{BUCKET}/temp',
        staging_location=f'gs://{BUCKET}/staging',
        job_name='clean-and-transform-merged-dataset'
    )

    def __init__(self):
        self.stop_words = set([...]) # Your list of stop words    
        
    def log_data(self, element):
        logging.info(f"Processing element: {element}")
        return element

    def parse_csv(self, element):
        """This function parses CSV rows into dictionaries."""
        if not element.strip(): # Skip empty lines
            return None
        try:
            reader = csv.DictReader([element])
            return next(reader)
        except StopIteration:
            return None

    def drop_columns(self, row):
        if not isinstance(row, dict):
            return None
        for column in ['images', 'videos', 'bought_together']:
            row.pop(column, None)
            return row

    def parse_details(self, element):
        if element is None:
            return None
        details = element.get('details', {})
        if isinstance(details, dict):
            element['package_dimensions'] = details.get('Package Dimensions')
            element['model_number'] = details.get('Item model number')
            element['first_available_date'] = details.get('Date First Available')
        else:
            element['package_dimensions'] = None
            element['model_number'] = None
            element['first_available_date'] = None
        element.pop('details', None)
        return element
        
    def convert_date(self, element):
        """Convert the 'first_available_date' string to year, month, day."""
        if element is None:
            return None
        date_str = element.get('first_available_date')
        if date_str:
            try:
                date = datetime.strptime(date_str, '%B %d, %Y') # Adjust format as needed
                element['year'] = date.year
                element['month'] = date.month
                element['day'] = date.day
            except ValueError as e:
                logging.error(f"Error parsing date '{date_str}': {e}")
                element['year'] = None
                element['month'] = None
                element['day'] = None
        return element
            
    def preprocess_description(self, element):
        """Preprocess the product description."""
        if element is None:
            return None
        description = element.get('description', '')
        if isinstance(description, list):
            description = ' '.join(description)
        description = description.lower()
        description = re.sub(r'[^a-z\s]', '', description)
        tokens = description.split() # Basic tokenization by whitespace
        tokens = [word for word in tokens if word not in self.stop_words]
        element['description'] = tokens
        return element
        
    def remove_empty_values(self, element):
        """Remove elements that have empty values."""
        if element is None:
            return False
        if not element.get('categories') and element.get('main_category'):
            element['categories'] = element['main_category']
        if all(value is None for key, value in element.items() if key != 'categories'):
            return False
        return True
        
    def run_pipeline(self, input_file, output_file):
        """Run the Apache Beam pipeline."""
        with beam.Pipeline(options=self.pipeline_options) as pipeline:
            merged_data = (
                pipeline
                | 'Read CSV Data' >> beam.io.ReadFromText(input_file, skip_header_lines=1)
                | 'Parse CSV' >> beam.Map(self.parse_csv)
                | 'Drop Columns' >> beam.Map(self.drop_columns)
                | 'Log Parsed Data' >> beam.Map(self.log_data) # Log parsed data
                | 'Parse Details' >> beam.Map(self.parse_details)
                | 'Convert Date' >> beam.Map(self.convert_date)
                | 'Preprocess Description' >> beam.Map(self.preprocess_description)
                | 'Remove Empty Values' >> beam.Filter(self.remove_empty_values)
                | 'Log Filtered Data' >> beam.Map(self.log_data) # Log after filtering
            )
            (merged_data
            | 'Write Output' >> beam.io.WriteToText(output_file, file_name_suffix='.json',
            num_shards=1)
            )

def run_pipeline(input_file, output_file):
    processor = OntologyProcessor()
    processor.run_pipeline(input_file, output_file)