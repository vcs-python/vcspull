
def expand_config(config):
    '''Expand configuration into full form.

    end-user configuration permit inline configuration shortcuts, expand to
    identical format for parsing.

    :param config: the repo config in :py:class:`dict` format.
    :type config: dict
    '''
    for directory, repos in config.iteritems():
        for repo, repo_data in repos.iteritems():

            '''
            repo_name: http://myrepo.com/repo.git

            to

            repo_name: { repo: 'http://myrepo.com/repo.git' }

            also assures the repo is a :py:class:`dict`.
            '''

            if isinstance(repo_data, basestring):
                config[directory][repo] = {'repo': repo_data}

            '''
            ``shell_command_after``: if str, turn to list.
            '''
            if 'shell_command_after' in repo_data:
                if isinstance(repo_data['shell_command_after'], basestring):
                    repo_data['shell_command_after'] = [
                        repo_data['shell_command_after']]

    return config


def get_repos(config):
    """ return a :py:obj:`list` list of repos from (expanded) config file.

    :param config: the expanded repo config in :py:class:`dict` format.
    :type config: dict
    """
    repo_list = []
    for directory, repos in config.iteritems():
        for repo, repo_data in repos.iteritems():
            repo_dict = {
                'name': repo,
                'parent_path': directory,
                'remote_location': repo_data['repo'],
            }

            if 'remotes' in repo_data:
                repo_dict['remotes'] = []
                for remote_name, remote_location in repo_data['remotes'].iteritems():
                    remote_dict = {
                        'remote_name': remote_name,
                        'remote_location': remote_location
                    }
                    repo_dict['remotes'].append(remote_dict)
            repo_list.append(repo_dict)
    return repo_list
