import streamlit as st
import yaml
import os


def create_yaml_from_secrets():
    config_path = "config.yaml"

    if not os.path.exists(config_path):
        secrets = st.secrets._dict

        with open(config_path, "w") as yaml_file:
            yaml.dump(secrets, yaml_file, default_flow_style=False)

        print(f"Config yaml:  {config_path} created!")
    else:
        print(f"Config yaml already exists!")


create_yaml_from_secrets()
