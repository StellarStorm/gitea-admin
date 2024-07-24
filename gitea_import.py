#!/bin/env python3
"""
Import external projects to a Gitea organization

Copyright (C) 2024 S. Gay
"""

import json
import logging
import os
from io import BytesIO
from urllib.parse import urlparse

import pycurl
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_format)
logger.addHandler(console_handler)

err_fh = logging.FileHandler('errors.log')
err_fh.setFormatter(log_format)
err_fh.setLevel(logging.ERROR)
logger.addHandler(err_fh)

load_dotenv()
GITEA_TOKEN = os.getenv('GITEA_ADMIN_TOKEN')

GITEA_DOMAIN = os.getenv('GITEA_DOMAIN')
GITEA_ORGANIZATION = 'RPA-Dependencies'


def import_repo(url: str, headers: list, post_data: str) -> int:
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.POSTFIELDS, post_data)
    c.setopt(c.HTTPHEADER, headers)
    c.setopt(c.WRITEDATA, buffer)
    c.perform()
    status = c.getinfo(c.RESPONSE_CODE)
    c.close()
    return status


if __name__ == '__main__':
    headers = [
        'accept: application/json',
        f'Authorization: token {GITEA_TOKEN}',
        'Content-Type: application/json',
    ]

    data = {
        'mirror': True,
        'private': True,
        'service': 'git',
        'uid': 0,
        'wiki': True,
    }
    with open('repos.txt') as f:
        repos = f.readlines()

    repos = [x.strip() for x in repos]
    for repo in repos:
        o = urlparse(repo)
        name = o.path.split('/')[-1]

        data['clone_addr'] = repo
        data['repo_name'] = name
        data['repo_owner'] = GITEA_ORGANIZATION
        post_data = json.dumps(data)
        url = f'{GITEA_DOMAIN}/api/v1/repos/migrate'
        status = import_repo(url, headers=headers, post_data=post_data)

        if status == 201:
            logger.info(f'Imported {name}')
        elif status == 409:
            logger.info(f'Skipping {name} as it already exists')
        elif status == 422:
            logger.error(f'Issue with the import data for {name}')
        else:
            logger.error(f'Code {status} for {name}')
