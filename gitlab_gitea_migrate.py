#!/bin/env python3
"""
Find GitLab projects & backup as mirrors to Gitea

Copyright (C) 2024 S. Gay
"""

import json
import logging
import os

import gitlab
import urllib3
from dotenv import load_dotenv

from gitea_import import import_repo

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_format)
logger.addHandler(console_handler)

err_fh = logging.FileHandler('gl_migrate_errors.log')
err_fh.setFormatter(log_format)
err_fh.setLevel(logging.ERROR)
logger.addHandler(err_fh)

load_dotenv()
GITEA_TOKEN = os.getenv('GITEA_ADMIN_TOKEN')

GITEA_DOMAIN = os.getenv('GITEA_DOMAIN')
GITEA_REPO_OWNER = 'Courtyard'

GITLAB_DOMAIN = os.getenv('GITLAB_DOMAIN')
GITLAB_TOKEN = os.getenv('GITLAB_UNPRIV_TOKEN')
GITLAB_GROUP = 'Courtyard'


def recursive_project_search(group, gl_instance):
    """
    Recursively search through a given GitLab group for all projects

    Args:
        group:              A GitLab group object (returned by `gl.groups.get`)

        gl_instance:        A valid GitLab instance

    Returns:
        A list of the namespace paths to all GitLab projects in the provided
        group
    """
    projects = [
        prj.attributes['path_with_namespace']
        for prj in group.projects.list(all=True)
    ]
    subgroups = [
        sub.attributes['full_path'] for sub in group.subgroups.list(all=True)
    ]

    while subgroups != []:
        for sub in subgroups:
            expanded = gl_instance.groups.get(sub)
            for new_sub in expanded.subgroups.list(all=True):
                subgroups.append(new_sub.attributes['full_path'])
            for prj in expanded.projects.list(all=True):
                projects.append(prj.attributes['path_with_namespace'])
            subgroups.remove(sub)

    return projects


if __name__ == '__main__':
    urllib3.disable_warnings()  # Silence warning for unverified HTTPS requests
    gl = gitlab.Gitlab(
        url=GITLAB_DOMAIN, private_token=GITLAB_TOKEN, ssl_verify=False
    )
    gl.auth()

    main_group = gl.groups.get(GITLAB_GROUP)

    logger.info('Finding projects on GitLab')
    repos = recursive_project_search(main_group, gl)
    repos = [
        r.replace(GITLAB_GROUP + '/', '')
        for r in repos
        if r.startswith(GITLAB_GROUP)
    ]

    headers = [
        'accept: application/json',
        f'Authorization: token {GITEA_TOKEN}',
        'Content-Type: application/json',
    ]
    data = {
        'lfs': False,
        'mirror': True,
        'private': True,
        'service': 'git',
        'uid': 0,
        'wiki': True,
        'issues': True,
        'labels': True,
        'milestones': True,
        'pull_requests': True,
        'releases': True,
        'wiki': True,
    }
    imported = 0
    skipped = 0
    errors = 0
    for repo in repos:
        name = repo.replace('/', '_')

        data['clone_addr'] = f'{GITLAB_DOMAIN}/{GITLAB_GROUP}/{repo}'
        data['auth_token'] = GITLAB_TOKEN
        data['repo_name'] = name
        data['repo_owner'] = GITEA_REPO_OWNER
        post_data = json.dumps(data)

        url = f'{GITEA_DOMAIN}/api/v1/repos/migrate'

        status = import_repo(url, headers=headers, post_data=post_data)
        if status == 201:
            logger.info(f'Imported {name}')
            imported += 1
        elif status == 409:
            logger.debug(f'Skipping {name} as it already exists')
            skipped += 1
        elif status == 422:
            logger.error(f'Issue with the input data for {name}')
            errors += 1
        else:
            logger.error(f'Code {status} for {name}')
            errors += 1
    logger.info(
        f'There were {imported} repos imported, {skipped} existing and skipped, and {errors} with errors'
    )
