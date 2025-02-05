# KGRecommender

# Installation and Deployment

Click the green "<> Code" button, then Open with Github Desktop.

Github Desktop will prompt you for a location to download the code repository to. Continue with your selection to add the folder /KGRecommender to your selected file location.

## CLoud Setup

### Google Cloud Setup

Make sure you have Owner privileges to the Google Cloud project.

Edit the following in utils/rag_constants.py to your own values:
	
	PROJECT_ID

[Install the Google Cloud command line interface](https://cloud.google.com/sdk/docs/install-sdk) (gcloud CLI).

Generate authentication for gcloud

	gcloud auth application-default login

Check which service account is being used

	gcloud auth list

### GCP Cloud Storage

To set up the preprocessing pipeline:

1. Upload the merged dataset (`merged_datasets2.csv`) to the top level of your Cloud Storage.
2. Create two folders, /temp and /staging at the top level of Cloud Storage.
3. (Optional) Turn off "Soft Delete" on your bucket to reduce charges by clearing out temp and staging files as soon as they're deleted (instead of keeping them around for the "soft delete" duration.

Edit the following in utils/rag_constants.py to your own values:
	
	REGION
	BUCKET

### GCP BigQuery

You can also upload `sample_data/giftcard.csv` data to BigQuery instead of using the local copy included in this repository.

Edit the following in utils/rag_constants.py to your own values:

	DATASET_ID
	TABLE_ID

### GCP Dataflow API

In GCP Console, search for DataFlow API (*not* Dataflow). Enable it.

**Create a Service Account**

Create a service account following the [guide on Application Default Credentials](https://cloud.google.com/docs/authentication/provide-credentials-adc)

	Create a service account with the roles your application needs, and a key for that service account, by following the instructions in Creating a service account key.
	Set the environment variable GOOGLE_APPLICATION_CREDENTIALS to the path of the JSON file that contains your credentials. This variable applies only to your current shell session, so if you open a new session, set the variable again.

Get a key for the service account following this [guide to create and delete service account keys](https://cloud.google.com/iam/docs/keys-create-delete#iam-service-account-keys-create-console). Create and save the key as a JSON file.

### GCP Neo4j Aura Integration Service & Neo4J Aura

From the GCP console, search for Neo4j Aura and subscribe to it. Then Enable it.

Click "Manage via Neo4J" which will bring you to Neo4J's website. Create an AuraDB instance and select AuraDB Professional. See also the instructions from [Neo4j's Docs](https://neo4j.com/docs/aura/auradb/getting-started/create-database/).

Edit the following in utils/rag_constants.py to your own values:

	NEO4J_URI
	NEO4J_USERNAME
	NEO4J_PASSWORD

### GCP Vertex AI

Enable Vertex AI in the GCP Console for your project.

### Deploy to Google App Engine

Enable Google App Engine.

	gcloud init
	gcloud app create

Create the app in the same region as your bucket and other resources.

Initialize GCP docker to let Google App Engine deploy to it.
In the GCP Console, navigate to Artifact Registry > Repositories > Setup instructions. Run the command listed, which should be something like:

	gcloud auth configure-docker us-docker.pkg.dev

Deploy the app to Google App Engine. Change to the directory with app.yaml in it.
	cd KGRecommender/app
	gcloud app deploy

After deployment, the web app at https://PROJECT_ID.REGION_ID.r.appspot.com e.g., https://deft-return-439619-h9.uw.r.appspot.com
or run 
	gcloud app browse

Go to IAM and find the service account for the deployed google cloud app. Assign it the following roles:
* Dataflow Admin
* Storage Admin
* Storage Object Admin
* Secret Manager Secret Accessor
* Secret Manager Viewer
* Vertex AI User
* Vertex AI Administrator

## Local Setup

### Neo4J Desktop

You can connect to a local Neo4J Desktop instance instead of one hosted on GCP.

Install and run Neo4j Desktop.

Edit the following in utils/rag_constants.py to your own values. Below are the default values for a fresh installation of Neo4J Desktop.

	NEO4J_URI = "bolt://localhost:7687"
	NEO4J_USERNAME = "neo4j"
	NEO4J_PASSWORD
	GRAPH_NAME = 'myGraph'

### Run Locally On Sample Data

Start Neo4j Desktop.
Start the default Neo4j database.

In a console, navigate to the KGRecommender folder and run

	jupyter notebook

In Jupyter Notebook, open sample.ipynb

Run the cells to load the knowledge graph into your local neo4J database.

## Set up Local Environment

Create a local isolated python environment, so the dependencies needed for this application won't interfere with other applications:
	cd KGRecommender
	python -m venv env
	.\env\Scripts\activate

To deactivate the environment, run the following command and delete the KGRecommender/env directory.
	deactivate
	rmdir /s /q env

### Install Python Dependencies

	cd KGRecommender/app
	pip install -r requirements.txt

## Run Frontend Locally

Run in a console:
	python app/main.py
Then visit http://localhost:5000 in a web browser to access the frontend.
