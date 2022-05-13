#/bin/env python3
import argparse
import boto3
from os.path import exists
import yaml
from pathlib import Path
import time
from tabulate import tabulate


client = boto3.client('cloudformation')

## main()
def main():
    ## parser and arguments
    parser = argparse.ArgumentParser(description="Managing AWS Cloudformation stacks.")
    parser.add_argument('-o', '--operation', required=True,help="Operation to perform. create or delete")
    parser.add_argument('-a', '--action', required=True,help="Operation to perform. plan or apply")
    parser.add_argument('-t', '--template',  required=True,help="Cloudformation template to operate")
    parser.add_argument('-v', '--variables',  required=True,help="YAML file holding cfn template variables")
    parser.add_argument('-c', '--changeset',  required=False,help="If creating a changeset not deployment straight, you can specify changeset name here")
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

    # action
    if (args.operation == 'create' and args.action == 'plan'):
        action = 'plan'
    elif (args.operation == 'create' and args.action == 'apply'):
        action = 'apply'
    else:
        print("Invalid option -a. Only specify when --operation is 'create'. Valid values are 'plan' or 'apply'")
        exit(1)

    # changeset name
    changeset = None
    if (args.changeset != None and args.changeset != ''):
        changeset = args.changeset

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
    if 'tags' in vars:
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
            time.sleep(5)
        else:
            break

    ## create / update stack
    if (operation == 'create'):
        # create changeset for new stack
        if (status == False):
            if (action == 'plan'):
                print(f'Creating changeset {changeset} ...')
                response = client.create_change_set(
                    StackName = stack_name,
                    ChangeSetName = changeset,
                    TemplateBody = Path(template).read_text(),
                    Parameters = parameters,
                    ChangeSetType = 'CREATE',
                    Tags = tags,
                    Capabilities=['CAPABILITY_IAM','CAPABILITY_NAMED_IAM','CAPABILITY_AUTO_EXPAND']
                )
                describe = client.describe_change_set(
                    ChangeSetName = changeset,
                    StackName = stack_name
                )
                print_changeset(describe)

            if (action == 'apply'):
                print(f'Applying changeset {changeset} ...')

                response = client.execute_change_set(
                    ChangeSetName = changeset,
                    StackName = stack_name,
                    DisableRollback = False
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
            # create change set for existing stack (update)
            if (action == 'plan'):
                print(f'Creating changeset {changeset} ...')
                response = client.create_change_set(
                    StackName = stack_name,
                    ChangeSetName = changeset,
                    TemplateBody = Path(template).read_text(),
                    Parameters = parameters,
                    ChangeSetType = 'UPDATE',
                    Tags = tags,
                    Capabilities=['CAPABILITY_IAM','CAPABILITY_NAMED_IAM','CAPABILITY_AUTO_EXPAND']
                )
                while True:
                    describe = client.describe_change_set(
                        ChangeSetName = changeset,
                        StackName = stack_name
                    )
                    if describe['Status'] == 'CREATE_PENDING':
                        print('Wait till creation finishes ...')
                        time.sleep(5)
                    else:
                        break
                print_changeset(describe)

            if (action == 'apply'):
                print(f'Applying changeset {changeset} ...')

                response = client.execute_change_set(
                    ChangeSetName = changeset,
                    StackName = stack_name,
                    DisableRollback = False
                )

                time.sleep(2)

                if (wait_for_status(stack_name, ['UPDATE_COMPLETE'], [
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
            if (idx > 120):
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

def print_changeset(description):
    print('Description')
    print('-----------------------')
    print(f'* StackName:       {description["StackName"]}')
    print(f'* ChangeSetName:   {description["ChangeSetName"]}')
    print(f'* ChangeSetId:     {description["ChangeSetId"]}')
    print(f'* ExecutionStatus: {description["ExecutionStatus"]}')
    print(f'* Status:          {description["Status"]}')
    if 'StatusReason' in description:
        print(f'* StatusReason:    {description["StatusReason"]}')
    if 'Changes' in description:
        print('* Changes:')
        data = []
        for change in description['Changes']:
            data.append(
                [
                    change['ResourceChange']['Action'],
                    change['ResourceChange']['LogicalResourceId'],
                    change['ResourceChange']['PhysicalResourceId'],
                    change['ResourceChange']['ResourceType'],
                    change['ResourceChange']['Replacement']
                ]
            )
        print(tabulate(data, headers=['Action', 'Logical ID', 'Physical ID', 'Resource type', 'Replacement']))
    #print(description)


## entry
if __name__ == '__main__':
    main()
