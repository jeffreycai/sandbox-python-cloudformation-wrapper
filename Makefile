## load .env
ifneq (,$(wildcard ./.env))
include .env
export
endif

# which environment to run against
ENVIRONMENT ?= dev

plan: var_pop
	python3 cloudformation.py -o create -t templates/cfn.yaml -v env/dev/cfn.yaml -c ${CHANGESET_NAME} -a plan

apply: var_pop
	python3 cloudformation.py -o create -t templates/cfn.yaml -v env/dev/cfn.yaml -c ${CHANGESET_NAME} -a apply

delete: var_pop
	python3 cloudformation.py -o delete -t templates/cfn.yaml -v env/dev/cfn.yaml 

pip_install:
	python3 -m pip install -r requires.txt

## pop var templates with env vars
var_pop:
	@ENVIRONMENT=${ENVIRONMENT} bash scripts/envpop.sh
