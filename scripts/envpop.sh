#!/bin/env bash

find "env/${ENVIRONMENT}" -name "*.tmpl" -exec bash -c 'envsubst < $1 > ${1%.tmpl}' _ {} \;
