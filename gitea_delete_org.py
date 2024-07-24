#!/bin/env python3

"""
Delete a Gitea organization and all its member repositories

Copyright (C) 2024 S. Gay

Inspired by
https://justyn.io/til/delete-all-repos-from-an-organization-in-forgejo-gitea/

"""

import argparse
import json
import logging
import os
from io import BytesIO

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
err_fh = logging.FileHandler('errors.log')
err_fh.setFormatter(log_format)
err_fh.setLevel(logging.ERROR)
logger.addHandler(err_fh)

load_dotenv()
GITEA_TOKEN = os.getenv('GITEA_ADMIN_TOKEN')

GITEA_DOMAIN = os.getenv('GITEA_DOMAIN')

headers = [
    'accept: application/json',
    f'Authorization: token {GITEA_TOKEN}',
    'Content-Type: application/json',
]


def search_repos(
    url: str, headers: list, page: int = 1, limit: int = 50
) -> list:
    """
    Gitea returns a max of 50 repositories (even for higher limit). This
    function allows recursive searching by varying the page that's being
    queried

    Args:
        url:        String, the REST API for an organization at which to search
                    for repositories. Should be of the format
                    `f'/api/v1/orgs/{org}/repos'`

        headers:    List of headers to pass to the API

        page:       Integer, the page for which to search for repositories

        limit:      Integer, the maximum number of repos to returns. Defaults
                    to 50. If this is set higher to 50, it will have no effect.

    Returns:
        List of repository names
    """
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, url + f'?page={page}&limit={limit}')
    c.setopt(c.HTTPHEADER, headers)
    c.setopt(c.WRITEDATA, buffer)
    c.perform()
    c.close()
    return json.loads(buffer.getvalue().decode('utf-8'))


def delete(url: str, headers: list) -> int:
    """
    Delete a Gitea object (repository or organization)

    Args:
        url:        String, the REST API url for the object to delete

        headers:    List of headers to pass to the API

    Returns:
        Integer, the response code of the operation
    """
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.HTTPHEADER, headers)
    c.setopt(pycurl.CUSTOMREQUEST, 'DELETE')
    c.setopt(c.WRITEDATA, buffer)
    c.perform()
    status = c.getinfo(c.RESPONSE_CODE)
    c.close()
    return status


if __name__ == '__main__':
    ap = argparse.ArgumentParser(
        formatter_class=argparse.MetavarTypeHelpFormatter,
        description='Delete a Gitea Organization',
        epilog='Copyright (C) 2024 S. Gay',
    )
    ap.add_argument(
        '--org',
        type=str,
        required=True,
        help='Name of Gitea organization to delete',
    )
    args = ap.parse_args()

    response = search_repos(
        url=f'{GITEA_DOMAIN}/api/v1/orgs/{args.org}/repos',
        page=1,
        headers=headers,
        limit=50,
    )
    repos = [x['name'] for x in response]

    count = len(repos)
    page = 2
    while count == 50:
        response = search_repos(
            url=f'{GITEA_DOMAIN}/api/v1/orgs/{args.org}/repos',
            page=page,
            headers=headers,
        )
        names = [x['name'] for x in response]
        repos.extend(names)
        page += 1
        count = len(names)

    logger.info(f'These repositories will be deleted: {repos}')

    for repo in repos:
        url = f'{GITEA_DOMAIN}/api/v1/repos/{args.org}/{repo}'
        status = delete(url, headers)
        if status == 204:
            logger.info(f'Deleted {repo}')
        else:
            logger.error(f'{repo} : {status}')

    url = f'{GITEA_DOMAIN}/api/v1/orgs/{args.org}'
    status = delete(url, headers)
    if status == 204:
        logger.info(f'Deleted organization {args.org}')
    else:
        logger.error(f'{args.org} : status')
