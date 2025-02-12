import json
import base64
import arrow
import requests
import jwt
import sys
import tkinter as tk
from tkinter import messagebox

PROPERTIES_FILES = {
    'Production': './pingid-prod.properties',
    'QA': './pingid-qa.properties',
    'DEV': './pingid-dev.properties'
}


class PingIDDriver:
    API_VERSION = '4.9.17'

    def __init__(self, properties_file, locale='en', verbose=False, verifyTls=True):
        self.locale = locale
        self.verbose = verbose
        self.verifyTls = verifyTls

        with open(properties_file) as f:
            lines = f.readlines()

        self.config = {}
        for line in lines:
            tuple = line.rstrip('\n').split('=', 1)
            if tuple[0] in ('idp_url', 'token', 'org_alias', 'use_base64_key'):
                self.config[tuple[0]] = tuple[1]

        base64_key = self.config.pop('use_base64_key')
        if self.verbose:
            print('{0}Properties{0}\n{1}\n'.format('=' * 20, self.config))

        self.config['key'] = base64.urlsafe_b64decode(base64_key)

        self.jwt_header = {
            'alg': 'HS256',
            'orgAlias': self.config['org_alias'],
            'token': self.config['token']
        }

        self.req_header = {
            'locale': self.locale,
            'orgAlias': self.config['org_alias'],
            'secretKey': self.config['token'],
            'version': self.API_VERSION
        }

    def call(self, end_point, req_body):
        timestamp = arrow.utcnow().format('YYYY-MM-DD HH:mm:ss.SSS')
        self.req_header['timestamp'] = timestamp
        key = self.config['key']

        req_payload = {
            'reqHeader': self.req_header,
            'reqBody': req_body
        }

        if self.verbose:
            print('{0}Request{0}\n{1}\n'.format('=' * 20, json.dumps(req_payload, indent=2)))

        url = self.config['idp_url'] + "/" + end_point

        req_jwt = jwt.encode(req_payload, key, algorithm='HS256', headers=self.jwt_header)

        if self.verbose:
            print('{0}Request Payload{0}\n{1}\n'.format('=' * 20, req_jwt))

        r = requests.post(url, req_jwt, headers={'Content-Type': 'application/json'}, verify=self.verifyTls)

        if self.verbose:
            print('Response status: {0}\n'.format(r.status_code))

        if self.verbose:
            print('{0}Response Payload{0}\n{1}\n'.format('=' * 20, r.content))

        if r.headers['content-type'] == 'application/octet-stream':
            extracted_response = r.text
        else:
            extracted_response = jwt.decode(r.content, key, algorithms=['HS256'])

        if self.verbose:
            print('{0}Response{0}\n{1}\n'.format('=' * 20, json.dumps(extracted_response, indent=2)))

        return extracted_response


def add_user(username, activateUser):
    req_body = {
        'activateUser': activateUser,
        'role': 'REGULAR',
        'userName': username,
    }
    pingid = PingIDDriver(selected_properties_file.get(), verbose=True)
    response_body = pingid.call('rest/4/adduser/do', req_body)
    return response_body


def get_user(username):
    req_body = {
        'getSameDeviceUsers': 'false',
        'userName': username,
    }
    pingid = PingIDDriver(selected_properties_file.get(), verbose=True)
    response_body = pingid.call('rest/4/getuserdetails/do', req_body)
    return response_body


def offline_pairing(username, sms):
    req_body = {
        'username': username,
        'type': 'SMS',
        'pairingData': sms,
    }
    pingid = PingIDDriver(selected_properties_file.get(), verbose=True)
    response_body = pingid.call('rest/4/offlinepairing/do', req_body)
    return response_body


def display_result(response):
    for widget in result_frame.winfo_children():
        widget.destroy()

    canvas = tk.Canvas(result_frame)
    scrollbar = tk.Scrollbar(result_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")
        )
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    if isinstance(response, dict) and 'userDetails' in response:
        user_details = response['userDetails']
        for i, (key, value) in enumerate(user_details.items()):
            tk.Label(scrollable_frame, text=key).grid(row=i, column=0, padx=10, pady=5, sticky=tk.W)
            tk.Label(scrollable_frame, text=value).grid(row=i, column=1, padx=10, pady=5, sticky=tk.W)
    else:
        tk.Label(scrollable_frame, text="No user details found").grid(row=0, column=0, padx=10, pady=10)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

def get_user_callback():
    username = username_entry.get()
    response = get_user(username)
    display_result(response)

def add_user_callback():
    username = username_entry.get()
    activate_user = activate_user_var.get()
    response = add_user(username, activate_user)
    display_result(response)

def offline_pairing_callback():
    username = username_entry.get()
    sms = sms_entry.get()
    response = offline_pairing(username, sms)
    display_result(response)


# Create the main window
root = tk.Tk()
root.title("PingID Tkinter App")
root.geometry("600x400")  # Set initial window size

# Create a menu
menu = tk.Menu(root)
root.config(menu=menu)

# Add menu items
pingid_menu = tk.Menu(menu)
menu.add_cascade(label="PingID", menu=pingid_menu)
pingid_menu.add_command(label="Get User", command=get_user_callback)
pingid_menu.add_command(label="Add User", command=add_user_callback)
pingid_menu.add_command(label="Offline Pairing", command=offline_pairing_callback)

# Create frames
input_frame = tk.Frame(root)
input_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

action_frame = tk.Frame(root)
action_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

result_frame = tk.Frame(root)
result_frame.grid(row=2, columnspan=2, padx=10, pady=10, sticky="nsew")

# Add labels and entry fields for user data in input frame
tk.Label(input_frame, text="Username:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=10)
username_entry = tk.Entry(input_frame)
username_entry.grid(row=0, column=1, padx=10, pady=10)

tk.Label(input_frame, text="SMS:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=10)
sms_entry = tk.Entry(input_frame)
sms_entry.grid(row=1, column=1, padx=10, pady=10)

activate_user_var = tk.BooleanVar()
tk.Checkbutton(input_frame, text="Activate User", variable=activate_user_var).grid(row=2, columnspan=2, padx=10, pady=10)

# Add environment selection frame
env_frame = tk.Frame(root)
env_frame.grid(row=1, columnspan=2, padx=10, pady=10, sticky="nsew")

selected_properties_file = tk.StringVar(value=PROPERTIES_FILES['Production'])

tk.Label(env_frame, text="Select Environment:").grid(row=0, column=0, padx=10, pady=10)
for i, (env, file) in enumerate(PROPERTIES_FILES.items()):
    tk.Radiobutton(env_frame, text=env, variable=selected_properties_file, value=file).grid(row=1, column=i, padx=10, pady=10)

# Add buttons for actions in action frame
tk.Button(action_frame, text="Get User", command=get_user_callback).grid(row=4, column=0, padx=2, pady=2)
tk.Button(action_frame, text="Add User", command=add_user_callback).grid(row=5, column=0, padx=2, pady=2)
tk.Button(action_frame, text="Offline Pairing", command=offline_pairing_callback).grid(row=6, column=0, padx=2, pady=2)

# Add a results frame
result_frame = tk.Frame(root)
result_frame.grid(row=2, columnspan=2, padx=10, pady=10, sticky="nsew")

# Make the frames resizable
root.grid_rowconfigure(0, weight=1)
root.grid_rowconfigure(1, weight=1)
root.grid_rowconfigure(2, weight=1)
root.grid_columnconfigure(0, weight=1)
root.grid_columnconfigure(1, weight=1)

# Start the application
root.mainloop()
