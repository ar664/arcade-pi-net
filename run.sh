#!/bin/bash

echo 'Setting environment...'
source "$(pwd)/venv/bin/activate"	
streamlit run main.py --server.port 8080
