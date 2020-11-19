# Python Script to create users on the Tableau Server
## Importing libraries
import os, argparse, keyring, re, configparser, warnings, urllib, requests, webbrowser
from datetime import time, datetime
from getpass import getpass
from pathlib import Path
warnings.filterwarnings('ignore')
config = configparser.ConfigParser()
config.read(r".\lic_create.cfg")

##Parsing arguments
parser = argparse.ArgumentParser(prog="tableau-user-create", description="Create new users on the Tableau Server with details and groups assigned")
parser.add_argument("--tableau-username", "-u", dest="tableau_username", required=True, type=str, help="Username of an admin user who can create new users on the site.")
parser.add_argument("--password", "-p", dest="password", default ="", required=False, type=str, help="Password for user (defaults to prompting user)")
parser.add_argument("--user-details-file", "-f", dest="user_list", required=True, type=str, help="List of users with their details to be added and group information.")

args = parser.parse_args()

## Functions
### Fn to check errors
def check_error(request, task):
    if task == "sign_in":
        if request.status_code == 200:
            print("\t\tUser signed in successfully!")
            return 1
        elif request.status_code == 404:
            print("\t\tERROR: User not found!!")
            return 0
        elif request.status_code == 401:
            print("\t\tERROR: Login error!!")
            return 0
        else:
            print("\t\tERROR: Request error check again!!")
            return 0
        
    elif task == "sign_out":
        if request.status_code == 204:
            print("\t\tUser signed out successfully!")
            return 1
        else:
            print("\t\tERROR: Request error check again!!")
            return 0
        
    elif task == "create_users":
        if request.status_code == 201:
            print("\t\tUser created successfully!")
            return 1
        elif request.status_code == 404:
            print("\t\tERROR: Site not found!!")
            return 0
        elif request.status_code == 409:
            print("\t\tERROR: User exists or license unavailable, check again!!")
            return 0
        elif request.status_code == 400:
            print("\t\tERROR: Invalid site role or bad request!!")
            return 0
        else:
            print("\t\tERROR: Request error check again!!")
            return 0
        
    elif task == "update_users":
        if request.status_code == 200:
            print("\t\tUser information updated successfully!")
            return 1
        elif request.status_code == 404:
            print("\t\tERROR: User or Site not found!!")
            return 0
        elif request.status_code == 409:
            print("\t\tERROR: User exists or license unavailable, check again!!")
            return 0
        elif request.status_code == 400:
            print("\t\tERROR: Invalid site role, email address or bad request!!")
            return 0
        elif request.status_code == 403:
            print("\t\tERROR: Licensing update on self or guest account not allowed!!")
            return 0
        else:
            print("\t\tERROR: Request error check again!!")
            return 0
        
    elif task == "find_group_id":
        if request.status_code == 200:
            print("\t\tGroup found!")
            return 1
        elif request.status_code == 404:
            print("\t\tERROR: Site not found!!")
            return 0
        else:
            print("\t\tERROR: Request error check again!!")
            return 0
        
    elif task == "add_user_group":
        if request.status_code == 200:
            print("\t\tUser added to group successfully!")
            return 1
        elif request.status_code == 404:
            print("\t\tERROR: Site or Group not found!!")
            return 0
        elif request.status_code == 409:
            print("\t\tERROR: Specified User already in group!!")
            return 0
        else:
            print("\t\tERROR: Request error check again!!")
            return 0


### Fn to sign in to Server
def sign_in(username, password, site=""):
    body = {
        "credentials": {
            "name": username,
            "password": password,
            "site": {
                "contentUrl": site
            }
        }
    }
    response = requests.post(
        URL + '/auth/signin', 
        json=body, 
        verify=False, 
        headers={'Accept': 'application/json'}
    )
    
    status = check_error(response, "sign_in")
    if status:
        return response.json()['credentials']['site']['id'], response.json()['credentials']['token']
    else:
        return 0,0
    

### Fn to sign out from Server
def sign_out(site_id, token):
    response = requests.post(
        URL + '/auth/signout', 
        verify=False, 
        headers={'Accept': 'application/json',
                'X-Tableau-Auth': token}
    )
    status = check_error(response, "sign_out")
    return status


### Fn to add users to the site
def create_users(site_id, token, user_name, site_role):
    create_user_body = {
        "user": {
            "name": user_name,
            "siteRole": site_role
        }
    }
        
    query_response = requests.post(
        URL + '/sites/{}/users'.format(site_id), 
        json=create_user_body,
        verify=False, 
        headers={
            'Accept': 'application/json',
            'X-Tableau-Auth': token
        }
    )
    
    status = check_error(query_response, "create_users")
    
    if status:
        user_id = query_response.json()['user']['id']
        return query_response.json(), user_id
    else:
        return 0,0


### Fn to update users details
def update_users(site_id, token, user_id, full_name, email, site_role):
    update_user_body = {
        "user": {
            "fullName": full_name,
            "email": email,
            "password": email+full_name,
            "siteRole": site_role
        }
    }
        
    query_response = requests.put(
        URL + '/sites/{}/users/{}'.format(site_id, user_id), 
        json=update_user_body,
        verify=False, 
        headers={
            'Accept': 'application/json',
            'X-Tableau-Auth': token
        }
    )
    
    status = check_error(query_response, "update_users")
    
    if status:
        return query_response.json()
    else:
        return 0


### Fn to find group id
def find_group_id(site_id, token, group_name):
    query_response = requests.get(
        URL + '/sites/{}/groups?filter=name:eq:{}'.format(site_id, group_name), 
        verify=False, 
        headers={
            'Accept': 'application/json',
            'X-Tableau-Auth': token
        }
    )
    
    status = check_error(query_response, "find_group_id")
    
    if status:
        group_id = query_response.json()['groups']['group'][0]['id']
        return query_response.json(), group_id
    else:
        return 0,0


### Fn to add user to group
def add_user_group(site_id, token, user_id, group_list):
    success_count = 0
    for group in group_list:
        response = find_group_id(site_id, token, group)
        if response[0] == 0:
            print("ERROR while searching for group {}".format(group))
            break

        user_id_body = {
            "user": {
                "id": user_id
            }
        }    

        query_response = requests.post(
            URL + '/sites/{}/groups/{}/users'.format(site_id, response[1]),
            json=user_id_body,
            verify=False, 
            headers={
                'Accept': 'application/json',
                'X-Tableau-Auth': token
            }
        )
        
        status = check_error(query_response, "add_user_group")
        if status == 0:
            print("ERROR while adding user to group {}".format(group))
            break
        else:
            success_count += status
    
    if success_count == len(group_list):
        return 1
    else:
        return 0


### Fn to parse user details from text file
def parse_user_list(user):
    user_attributes = user.split(";")
    user_dict = {}
    if "SAMPLE" not in user_attributes[1]:
        user_dict['action'] = user_attributes[0].lstrip()
        user_dict['action'] = user_dict['action'].rstrip()
        user_dict['user_name'] = user_attributes[1].lstrip()
        user_dict['user_name'] = user_dict['user_name'].rstrip()
        user_dict['full_name'] = user_attributes[2].lstrip()
        user_dict['full_name'] = user_dict['full_name'].rstrip()
        user_dict['email'] = user_attributes[3].lstrip()
        user_dict['email'] = user_dict['email'].rstrip()
        user_dict['site_role'] = user_attributes[4].lstrip()
        user_dict['site_role'] = user_dict['site_role'].rstrip()
        if user_dict['site_role'].lower() == 'yellow':
            user_dict['site_role'] = "Viewer"
        elif user_dict['site_role'].lower() == 'green':
            user_dict['site_role'] = "ExplorerCanPublish"
        elif user_dict['site_role'].lower() == 'blue':
            user_dict['site_role'] = "Creator"
        temp_list = (((user_attributes[5]).split("[")[1]).split("]")[0]).split(',')
        user_dict['groups'] = []
        for item in temp_list:
            user_dict['groups'].append(urllib.parse.quote_plus(item))
    return user_dict


### Fn to generate email to new users
def gen_email(full_name, email, user_name, action):
    cc = "praveen.sam@biztory.com"
    first_name = full_name.split(" ")[0]
    first_name = urllib.parse.quote(first_name)
    if action.lower() == 'create':
        subject = "Tableau Server account created!"
        subject = urllib.parse.quote(subject)
        body="Hello {}!\n\nYour account has now been set up in Tableau Server with your PNL as user name.\nTableau is connected to SAML (Single Sign On) so you get automatically logged in when you go to the Tableau server. Please make sure that you have the ‘Tableau role’ within TimTam. If this is not the case you receive the message ‘access forbidden’. To get this Tableau role, reach out to the TimTam contact person of your domain and ask for the Tableau Role.\n\nThe Tableau Server can be reached at: https://penguin.biztory.com\n\nFor more information about Tableau and the Self Service Community you can check out the Confluence page\n\nYou can also contact your Key User for more information or for any issues with Tableau\n\nIf you have any questions or need any further assistance you can contact us on Slack\n\nKind Regards,\nThe Self Service Analytics Team".format(first_name)
        body=urllib.parse.quote(body)
        webbrowser.open("mailto:{}?cc={}&subject={}&body={}".format(email,cc,subject,body))
    elif action.lower() == 'pnl_correction':
        subject = "VERIFICATION of Tableau Server account username"
        subject = urllib.parse.quote(subject)
        body="Hello {}!\n\nThank you for your request for a Tableau Server account. We received '{}' as your Windows Login ID.\n\nWe are aware that there are exceptions to this rule however we wanted to confirm with you whether the Windows Login ID you provided is correct.\n\nYou can confirm this with us via email and then we can provision your account as soon as possible.\n\nIf you have any questions about your user name you can contact your Key User about it\n\nIf you need any further assistance you can contact us on Slack\n\nKind Regards,\nThe Self Service Analytics Team".format(first_name, user_name)
        body=urllib.parse.quote(body)
        webbrowser.open("mailto:{}?cc={}&subject={}&body={}".format(email,cc,subject,body))
    elif action.lower() == 'blue_belt_intake':
        subject = "Intake for Tableau Server Blue Belt"
        subject = urllib.parse.quote(subject)
        body="Hello {}!\n\nThank you for your request for a Tableau Server Blue Belt. We have a very limited number of Blue Belt licenses and thus require that every Blue Belt user has an intake to verify that this is the best license for you.\n\nA Blue Belt license will allow you to create new datasources and then publish them to develop dashboards via the Tableau Desktop application. However if you just want to publish dashboards based on existing datasources then a Green belt would be sufficient.\n\nIn the call we will discuss your use case and how we can provide you resources to get you started with Tableau.\n\nYou can reach out us on Slack to schedule this intake call at a time convenient for you or for any questions you may have.\n\nKind Regards,\nThe Self Service Analytics Team".format(first_name)
        body=urllib.parse.quote(body)
        webbrowser.open("mailto:{}?cc={}&subject={}&body={}".format(email,cc,subject,body))


## Variables
server = config["server_connection"]["server"] # Enter site in format tableau.company.com without the https before it
site_content_url = config["server_connection"]["site"] # This can be found from the URL of the content and if using the Default site then this will be blank
api_ver = config["server_connection"]["api"] # This can be found from the Tableau Server REST API reference
username = args.tableau_username # This is your username

URL = "https://{}/api/{}".format(server, api_ver)


## Open Log file
log_file_loc = r"{}\{}".format(str(Path.home()), config["logging_details"]["logfilename"])
log_file = open(log_file_loc, "a+")


## Sign in to the Tableau Server
password = args.password
if password == "":
    password = getpass("Enter your password for the Tableau Server: ")
    
site_id, token = sign_in(username, password, site_content_url)
if token == 0:
    exit()
    
    
## Read in User list
user_list_loc = args.user_list
user_list = open(user_list_loc, "r")
users = user_list.readlines()
user_attrib = []
for user in users:
    user_dict = parse_user_list(user)
    if len(user_dict) > 0:
        user_attrib.append(parse_user_list(user))
print("Parsed in {} records for processing...".format(len(user_attrib)))

## Create user and add to groups
for user in user_attrib:
    if user['action'] == 'create':
        print("\nAttempting to create an account for {} ({}) with a {} belt...".format(user['full_name'], user['user_name'], user['site_role']))
        create_response = create_users(site_id, token, user['user_name'], user['site_role'])
        if create_response[1] == 0:
            print("\n\nERROR while adding user {}".format(user))
            break

        update_response = update_users(site_id, token, create_response[1], user['full_name'], user['email'], user['site_role'])
        if update_response == 0:
            print("\n\nERROR while updating user details for {}".format(user))
            current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_file.write("\n{} WARNING: User {} created on Server with role {} but failed to update details".format(current_timestamp, user['user_name'], user['site_role']))
            break

        add_group_response = add_user_group(site_id, token, create_response[1], user['groups'])
        if add_group_response == 0:
            print("\n\nUser {}({}) not added to all groups mentioned!!")
            current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_file.write("\n{} WARNING: User {}({}) created on Server with role {} and email {} but not all groups added out of {}".format(current_timestamp, user['full_name'], user['user_name'], user['site_role'], user['email'], user['groups']))
        else:
            current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_file.write("\n{} User {}({}) created on Server and added to groups {} with role {} and email {}".format(current_timestamp, user['full_name'], user['user_name'], user['groups'], user['site_role'], user['email']))
        gen_email(user['full_name'], user["email"], user['user_name'], 'create')
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file.write("\n{} Email generated for {}({}) with role {} to email {}".format(current_timestamp, user['full_name'], user['user_name'], user['site_role'], user['email']))
        
    elif user['action'] == 'pnl_correction':
        print("\nGenerating an PNL correction email for {} ({}) with a {} belt...".format(user['full_name'], user['user_name'], user['site_role']))
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file.write("\n{} User {}({}) does not have PNL in a format that was expected".format(current_timestamp, user['full_name'], user['user_name']))
        gen_email(user['full_name'], user['email'], user['user_name'], 'pnl_correction')
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file.write("\n{} Email generated for Username correction for {}({}) with role {} to email {}".format(current_timestamp, user['full_name'], user['user_name'], user['site_role'], user['email']))
                       
    elif user['action'] == 'blue_belt_intake':
        print("\nGenerating email for Blue Belt intake for {} ({})...".format(user['full_name'], user['user_name']))
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file.write("\n{} User {}({}) requested a {} belt therefore intake is required".format(current_timestamp, user['full_name'], user['user_name'], user['site_role']))
        gen_email(user['full_name'], user["email"], user['user_name'], 'blue_belt_intake')
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file.write("\n{} Email generated for Blue Belt intake for {}({}) to email {}".format(current_timestamp, user['full_name'], user['user_name'], user['email']))
    
    else:
        print("\nUnknown action for {} ({}), skipping record!!".format(user['full_name'], user['user_name']))
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file.write("\n{} ERROR: User {}({}) had an incorrect action specified. The following is requested action: {}".format(current_timestamp, user['full_name'], user['user_name'], user['action']))


## Close files and sign out of server
log_file.close()
user_list.close()
sign_out(site_id, token)