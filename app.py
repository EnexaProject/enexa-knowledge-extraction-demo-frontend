import json
import streamlit as st
from streamlit.components.v1 import html

from PIL import Image
import base64
from io import StringIO 
import logging
import requests
import pprint
import os
import pprint

from decouple import config

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

# config
ENEXA_SHARED_DIRECTORY = config("ENEXA_SHARED_DIRECTORY")
# TODO: needs to be injected somehow
ENEXA_WRITEABLE_DIRECTORY = ENEXA_SHARED_DIRECTORY + "/experiment1"
ENEXA_LOGO = "https://raw.githubusercontent.com/EnexaProject/enexaproject.github.io/main/images/enexacontent/enexa_logo_v0.png?raw=true"

def write_file_to_folder(folder, filename, content):
    # create directory if not exists
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    with open(folder + "/" + filename, "wb") as f:
        f.write(content)


st.set_page_config(layout="wide", initial_sidebar_state="expanded",
    page_title="ENEXA Integration Demo",
#    page_icon=Image.open(ENEXA_LOGO)
)



st.title("ENEXA Integration Demo")

st.markdown(    
"""
This demo is showing the integration of the processing steps regarding the Class Expression Learning in ENEXA.

## Knowledge Extraction 

### Input: Upload JSON files with URLs for the knowledge extraction

Upload a JSON file containing one array of URLs to Wikipedia articles.

""")
#type=["txt"], 
uploaded_files = st.file_uploader("Upload a JSON file", accept_multiple_files=True, label_visibility="collapsed")

if uploaded_files is not None and uploaded_files != []:
    for uploaded_file in uploaded_files:
        
        # TODO: create IRI automatically by calling /start-experiment
        experiment_resource = "http://example.org/experiment1"
        relative_file_location_inside_enexa_dir = "experiment1"

        #uploaded_filename = "test1.txt" # uploaded_file.name
        uploaded_filename = uploaded_file.name.replace(" ", "_")
        uploaded_file_content = uploaded_file.read()
        
        write_file_to_folder(ENEXA_WRITEABLE_DIRECTORY, uploaded_filename, uploaded_file_content)
        
        st.info("File {} uploaded successfully and stored in experiment's directory: {}".format(uploaded_filename, ENEXA_WRITEABLE_DIRECTORY))

        ttl_for_registering_the_file_upload = """
        @prefix enexa:  <http://w3id.org/dice-research/enexa/ontology#> .
        @prefix prov:   <http://www.w3.org/ns/prov#> .

        [] a prov:Entity ; 
            enexa:experiment <{}> ; 
            enexa:location "enexa-dir:{}/{}" .
        """.format(experiment_resource, relative_file_location_inside_enexa_dir, uploaded_filename)

        st.code(ttl_for_registering_the_file_upload, language="turtle")

        # TODO: automate transformation from JSON-LD to Turtle

        ttl_for_registering_the_file_upload_as_jsonld = """
[
  {
    "@id": "_:nbe37201c48f0429e8206c483d785db79b1",
    "@type": [
      "http://www.w3.org/ns/prov#Entity"
    ],
    "http://w3id.org/dice-research/enexa/ontology#experiment": [
      {
        "@id": "http://example.org/experiment1"
      }
    ],
    "http://w3id.org/dice-research/enexa/ontology#location": [
      {
        "@value": "enexa-dir:experiment1/test1.json"
      }
    ]
  }
]
        """

        st.code(ttl_for_registering_the_file_upload_as_jsonld, language="json")

        SERVER_ENDPOINT = "http://localhost:8080"
        response = requests.post(SERVER_ENDPOINT + "/add-resource", data=ttl_for_registering_the_file_upload_as_jsonld, headers={"Content-Type": "application/ld+json"})

        if response.status_code == 200:
            st.success("ENEXA configuration file upload registered successfully.")
            st.code(pprint.pformat(response.json(), indent=2), language="json")
            file_id = response.json()["@id"]
            st.success("File ID for your ENEXA task: {}".format(file_id))
            
            st.info("Now, the ENEXA task should be started at the ENEXA platform. Please check the status of your task at the ENEXA platform.")
            st.info("Waiting for result ... (TODO)")
            
        else:
            st.error("Error while registering ENEXA configuration file upload.")
            st.error(response) 

# st.markdown("#### Upload (preliminary) T-Box data")

# generation_configuration_file= st.file_uploader("Upload a TTL file", type=["ttl"], accept_multiple_files=False, label_visibility="collapsed")

# st.markdown("#### Upload (preliminary) T-Box data")

# st.file_uploader("Upload a TTL file", type=["ttl"], accept_multiple_files=False, label_visibility="collapsed")

# st.markdown("#### Input schema (SPARQL endpoint)")

# input_schema = st.text_input("SPARQL endpoint", help="e.g., http://localhost:3030/ds/query")

# st.markdown("""
# #### SPARQL Queries (JSON-LD)

# Text: 

# ### Output

# **The result will be shown a RDF data file (TTL?).**

# **The result file will be handed to the ENEXA API for further processing.**

# """)

