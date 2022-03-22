#/bin/env python3
import argparse
import boto3
from os.path import exists
import yaml
from pathlib import Path
import time


client = boto3.client('cloudformation')

## main()
def main():
    ## parser and arguments
    parser = argparse.ArgumentParser(description="Managing AWS Cloudformation stacks.")
    parser.add_argument('-o', '--operation', required=True,help="Operation to perform. create or delete")
    parser.add_argument('-t', '--template',  required=True,help="Cloudformation template to operate")
    parser.add_argument('-v', '--variables',  required=True,help="YAML file holding cfn template variables")
    args = parser.parse_args()


    ## var validation / initialization
    # operation
    if (args.operation == "create"):
        operation = "create"
    elif (args.operation == "delete"):
        operation = "delete"
    else:
        print("Invalid option -o. Use 'create' or 'delete'")
        exit(1)

    # template
    if (exists(args.template)):
        template = args.template
    else:
        print(f"Template file {args.template} does not exist.")
        exit(1)

    # variable
    if (exists(args.variables)):
        variables = args.variables
    else:
        print(f"Variables file {args.variables} does not exist.")
        exit(1)

    ## load vars
    with open(variables, "r") as file:
        vars = yaml.safe_load(file)
    
    parameters = []
    for idx in range(len(vars['parameters'])):
        for key in vars['parameters'][idx]:
            parameters.append({
                'ParameterKey': key,
                'ParameterValue': vars['parameters'][idx][key]
            })

    tags = []
    for idx in range(len(vars['tags'])):
        for key in vars['tags'][idx]:
            tags.append({
                'Key': key,
                'Value': vars['tags'][idx][key]
            })

    stack_name = vars['StackName']
    status = get_stack_status(stack_name)

    # first, we wait till stack is good in stable status
    while(True):
        if status != False and "IN_PROGRESS" in status:
            print(f'Stack {stack_name} is still in action, wait till it is stable..')
            wait_for_status(stack_name, [
                'CREATE_FAILED',
                'CREATE_COMPLETE',
                'ROLLBACK_FAILED',
                'ROLLBACK_COMPLETE',
                'DELETE_FAILED',
                'DELETE_COMPLETE',
                'UPDATE_COMPLETE',
                'UPDATE_FAILED',
                'UPDATE_ROLLBACK_FAILED',
                'UPDATE_ROLLBACK_COMPLETE',
                'IMPORT_COMPLETE',
                'IMPORT_ROLLBACK_FAILED',
                'IMPORT_ROLLBACK_COMPLETE'
            ], [])
            sleep(5)
        else:
            break

    ## create / update stack
    if (operation == 'create'):
        # when stack not exists, create
        if (status == False):
            print('Creating stack ...')
            response = client.create_stack(
                StackName = stack_name,
                TemplateBody = Path(template).read_text(),
                Parameters = parameters,
                OnFailure = 'ROLLBACK',
                Tags = tags
            )

            time.sleep(2)

            if (wait_for_status(stack_name, ['CREATE_COMPLETE'], [
                    'CREATE_FAILED',
                    'ROLLBACK_FAILED',
                    'ROLLBACK_COMPLETE',
                    'DELETE_FAILED',
                    'DELETE_COMPLETE',
                    'UPDATE_COMPLETE',
                    'UPDATE_FAILED',
                    'UPDATE_ROLLBACK_FAILED',
                    'UPDATE_ROLLBACK_COMPLETE',
                    'IMPORT_COMPLETE',
                    'IMPORT_ROLLBACK_FAILED',
                    'IMPORT_ROLLBACK_COMPLETE'
                ])):
                print(f'Stack {stack_name} creation SUCCESSFUL!')
                exit(0)
            else:
                print(f'Stack {stack_name} creation FAILED!')
                exit(1)
    
        # when stack exists, update
        else:
            print('Updating stack ...')
            response = client.update_stack(
                StackName = stack_name,
                TemplateBody = Path(template).read_text(),
                Parameters = parameters,
                Tags = tags
            )
    
            time.sleep(2)

            if (wait_for_status(stack_name, ['UPDATE_COMPLETE'], [
                    'CREATE_FAILED',
                    'CREATE_COMPLETE',
                    'ROLLBACK_FAILED',
                    'ROLLBACK_COMPLETE',
                    'DELETE_FAILED',
                    'DELETE_COMPLETE',
                    'UPDATE_FAILED',
                    'UPDATE_ROLLBACK_FAILED',
                    'UPDATE_ROLLBACK_COMPLETE',
                    'IMPORT_COMPLETE',
                    'IMPORT_ROLLBACK_FAILED',
                    'IMPORT_ROLLBACK_COMPLETE'
                ])):
                print(f'Stack {stack_name} update SUCCESSFUL!')
                exit(0)
            else:
                print(f'Stack {stack_name} update FAILED!')
                exit(1)
                
    ## delete stack
    if (operation == 'delete'):
        # when stack not exists, no need to do anything
        if (status == False):
            print('Stack already gone.')
        else:
            print('Deleting stack ...')
            response = client.delete_stack(
                StackName = stack_name,
            )

            time.sleep(2)

            if (wait_for_status(stack_name, ['DELETE_COMPLETE'], [
                'CREATE_FAILED',
                'CREATE_COMPLETE',
                'ROLLBACK_FAILED',
                'ROLLBACK_COMPLETE',
                'DELETE_FAILED',
                'DELETE_COMPLETE',
                'UPDATE_COMPLETE',
                'UPDATE_FAILED',
                'UPDATE_ROLLBACK_FAILED',
                'UPDATE_ROLLBACK_COMPLETE',
                'IMPORT_COMPLETE',
                'IMPORT_ROLLBACK_FAILED',
                'IMPORT_ROLLBACK_COMPLETE'
            ]) == None):
                print(f'Stack {stack_name} delete SUCCESSFUL!')
                exit(0)
            else:
                print(f'Stack {stack_name} delete FAILED!')
                exit(1)




def wait_for_status(stack_name, success_status, failed_status, next_token = None):
    '''
    Wait and see if stack reaches a given status.
    return True if yes, or False not / Error occurs
    '''
    options = {
        'StackName': stack_name
    }

    if (next_token != None):
        options['NextToken'] = next_token

    try:
        idx = 0
        while(True):
            idx = idx +1
            if (idx > 60):
                print(f'Timeout waiting for Stack {stack_name}')
                return False

            response = client.describe_stacks(**options)
            status = response['Stacks'][0]['StackStatus']

            if status in success_status:
                return True
            elif status in failed_status:
                return False
            else:
                print(f' - waiting for Stack {stack_name}: {status}')
                time.sleep(5)
    except Exception as e:
        print(f'Error describing stack {stack_name}')
        return None

    if 'NextToken' in response.keys():
        return wait_for_status(stack_name, success_status, failed_status, response['NextToken'])


def get_stack_status(stack_name, next_token = None):
    '''
    Check if a given stack is in status other than 
    '''
    options = {
        'StackName': stack_name
    }

    if (next_token != None):
        options['NextToken'] = next_token

    try:
        response = client.describe_stacks(**options)
        status = response['Stacks'][0]['StackStatus']

        if status not in ['DELETE_COMPLETE']:
            return status
        else:
            return False
    except Exception as e:
        print(f'Error describing stack {stack_name}')
        return False

    if 'NextToken' in response.keys():
        return get_stack_status(stack_name, response['NextToken'])



## entry
if __name__ == '__main__':
    main()
