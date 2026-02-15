(cli-import-codecommit)=

# vcspull import codecommit

Import repositories from AWS CodeCommit.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: import codecommit
```

## Usage

CodeCommit does not require a target argument. Use `--region` and `--profile`
to select the AWS environment:

```console
$ vcspull import codecommit -w ~/code/ --region us-east-1 --profile work
```

## Authentication

- **Auth**: AWS CLI credentials (`aws configure`) — no token env var
- **CLI args**: `--region`, `--profile`
- **IAM permissions required**:
  - `codecommit:ListRepositories` (resource: `*`)
  - `codecommit:BatchGetRepositories` (resource: repo ARNs or `*`)
- **Dependency**: AWS CLI must be installed (`pip install awscli`)

Configure your AWS credentials:

```console
$ aws configure
```

Then import:

```console
$ vcspull import codecommit -w ~/code/ --region us-east-1
```
