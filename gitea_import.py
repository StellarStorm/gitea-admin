#!/bin/env python3
"""
Import external projects to a Gitea organization

Copyright (C) 2024 S. Gay
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests
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


def get_base_url() -> str:
    domain = GITEA_DOMAIN
    if domain is None:
        raise ValueError('GITEA_DOMAIN is not set in the environment')
    if not domain.startswith(('http://', 'https://')):
        domain = f'http://{domain}'
    return domain


def get_existing_repos(headers: dict) -> set[str]:
    base_url = get_base_url()
    logger.info(f'Getting existing repos in {GITEA_ORGANIZATION} at {base_url}')
    existing = set()
    page = 1
    while True:
        resp = requests.get(
            f'{base_url}/api/v1/orgs/{GITEA_ORGANIZATION}/repos',
            headers=headers,
            params={'page': page, 'limit': 50},
        )
        repos = resp.json()
        if not repos:
            break
        for r in repos:
            existing.add(r['name'])
        page += 1
    return existing


def import_repo(repo: str, headers: dict, base_data: dict) -> tuple[str, int]:
    o = urlparse(repo)
    name = o.path.split('/')[-1]

    data = base_data.copy()
    data['clone_addr'] = repo
    data['repo_name'] = name
    data['repo_owner'] = GITEA_ORGANIZATION

    url = f'{get_base_url()}/api/v1/repos/migrate'

    resp = requests.post(url, headers=headers, json=data)
    return name, resp.status_code


if __name__ == '__main__':
    workers = int(os.environ.get('WORKERS', 2))
    headers = {
        'accept': 'application/json',
        'Authorization': f'token {GITEA_TOKEN}',
    }

    base_data = {
        'mirror': True,
        'private': True,
        'service': 'git',
        'wiki': True,
    }
    with open('repos.txt') as f:
        repos = f.readlines()

    imported = 0
    skipped = 0
    errors = 0
    repos = [x.strip() for x in repos]

    existing = get_existing_repos(headers)
    logger.info(f'Found {len(existing)} existing repos in {GITEA_ORGANIZATION}')

    to_import = []
    for repo in repos:
        name = urlparse(repo).path.split('/')[-1]
        if name in existing:
            logger.info(f'Skipping {name} as it already exists')
            skipped += 1
        else:
            to_import.append(repo)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(import_repo, repo, headers, base_data): repo
            for repo in to_import
        }
        for future in as_completed(futures):
            name, status = future.result()

            if status == 201:
                logger.info(f'Imported {name}')
                imported += 1
            elif status == 409:
                logger.info(f'Skipping {name} as it already exists')
                skipped += 1
            elif status == 422:
                logger.error(f'Issue with the import data for {name}')
                errors += 1
            else:
                logger.error(f'Code {status} for {name}')
                errors += 1
    logger.info(
        f'There were {imported} repos imported, {skipped} existing and skipped, and {errors} with errors'
    )
