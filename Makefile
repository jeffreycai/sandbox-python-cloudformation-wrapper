## load .env
ifneq (,$(wildcard ./.env))
include .env
export
endif

# which environment to run against
ENVIRONMENT ?= dev

s3_create: var_pop
	python3 cloudformation.py -o create -t templates/s3.yaml -v env/dev/s3.yaml 

s3_delete: var_pop
	python3 cloudformation.py -o delete -t templates/s3.yaml -v env/dev/s3.yaml 

## pop var templates with env vars
var_pop:
	@ENVIRONMENT=${ENVIRONMENT} bash scripts/envpop.sh
