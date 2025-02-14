import yaml
from yaml.loader import SafeLoader

import streamlit_authenticator as stauth

with open('./config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

hash = stauth.Hasher.hash_passwords(config['credentials'])

print(hash)