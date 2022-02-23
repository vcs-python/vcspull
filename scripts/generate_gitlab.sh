#!/usr/bin/env bash

if [ -z "${GITLAB_TOKEN}" ]; then
    echo 'Please provide the environment variable $GITLAB_TOKEN'
    exit 1
fi

if [ $# -lt 2 ]; then
    echo "Usage: $0 <gitlab_host> <gitlab_namespace> [</path/to/target.config>]"
    exit 1
fi

prefix="$(pwd)"
gitlab_host="${1}"
namespace="${2}"
config_file="${3:-./vcspull.yaml}"

current_namespace_path=""

curl --silent --show-error --header "Authorization: Bearer ${GITLAB_TOKEN}" "https://${gitlab_host}/api/v4/groups/${namespace}/projects?include_subgroups=true&per_page=100" \
    | jq -r '.[]|.namespace.full_path + " " + .path' \
    | LC_ALL=C sort \
    | while read namespace_path reponame; do
        if [ "${current_namespace_path}" != "${namespace_path}" ]; then
            current_namespace_path="${namespace_path}"

            echo "${prefix}/${current_namespace_path}:"
        fi

        # simplified config not working - https://github.com/vcs-python/vcspull/issues/332
        #echo "  ${reponame}: 'git+ssh://git@${gitlab_host}/${current_namespace_path}/${reponame}.git'"

        echo "  ${reponame}:"
        echo "    url: 'git+ssh://git@${gitlab_host}/${current_namespace_path}/${reponame}.git'"
        echo "    remotes:"
        echo "      origin: 'ssh://git@${gitlab_host}/${current_namespace_path}/${reponame}.git'"
    done \
   | tee "${config_file}"
