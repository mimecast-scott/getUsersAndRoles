import requests
import json
import csv
import time

CLIENT_ID_HERE="<--YOUR-MIMECAST-2.0-ID-HERE-->"
CLIENT_SECRET_HERE = "<--YOUR-MIMECAST-2.0-SECRET-HERE-->"

LIMIT_RESULTS = -1 #50 
PAGE_SIZE = 100
MAX_RETRIES = 3


def get_bearer_token():
    url = "https://api.services.mimecast.com/oauth/token"
    payload = f'client_id={CLIENT_ID_HERE}&client_secret={CLIENT_SECRET_HERE}&grant_type=client_credentials'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    for attempt in range(MAX_RETRIES):
        response = requests.post(url, headers=headers, data=payload)
        if response.status_code == 200:
            print("Token acquired successfully.")
            return response.json().get('access_token')
        else:
            print(f"Error getting bearer token (Attempt {attempt + 1}/{MAX_RETRIES}):", response.json())
            time.sleep(2)  # Short delay before retrying
    print("Failed to obtain bearer token after multiple attempts.")
    return None


def handle_rate_limit(response):
    rate_limit_reset = response.headers.get('X-RateLimit-Reset')
    if rate_limit_reset:
        wait_time = int(rate_limit_reset) - int(time.time())
        if wait_time > 0:
            print(f"Rate limit exceeded. Waiting {wait_time} seconds.")
            time.sleep(wait_time)


def get_users(bearer_token):
    url = "https://api.services.mimecast.com/api/user/get-internal-users"
    users = []
    page_token = None
    count = 0
    
    while True:
        payload = {"meta": {"pagination": {"pageSize": PAGE_SIZE}}}
        if page_token:
            payload["meta"]["pagination"]["pageToken"] = page_token
        
        headers = {'Authorization': f'Bearer {bearer_token}'}
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 401:
            print("Token expired. Refreshing token.")
            new_token = get_bearer_token()
            if not new_token:
                print("Failed to refresh token. Exiting.")
                break
            bearer_token = new_token  # Update the bearer_token variable
            continue
        elif response.status_code == 429:
            handle_rate_limit(response)
            continue
        elif response.status_code != 200:
            print(f"Error fetching users: {response.status_code}", response.json())
            break

        response_data = response.json()
        users.extend(response_data.get('data', [])[0].get('users', []))
        page_token = response_data.get('meta', {}).get('pagination', {}).get('next')
        print(f"Page {count}: {page_token}")
        count += 1
        if not page_token or count == LIMIT_RESULTS:
            break
    
    return users, bearer_token  # Return both users and potentially updated token


def get_user_role(email, bearer_token):
    url = "https://api.services.mimecast.com/api/user/get-profile"
    payload = json.dumps({"data": [{"showAvatar": False, "emailAddress": email}]})
    
    for attempt in range(MAX_RETRIES):
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {bearer_token}'}
        response = requests.post(url, headers=headers, data=payload)
        
        if response.status_code == 401:
            print("Token expired while fetching user role. Refreshing token.")
            new_token = get_bearer_token()
            if not new_token:
                print("Failed to refresh token. Skipping user.")
                return None, bearer_token
            bearer_token = new_token  # Update the bearer_token variable
            continue
        elif response.status_code == 429:
            handle_rate_limit(response)
            continue
        elif response.status_code == 200:
            response_data = response.json()
            if response_data.get('data') and len(response_data['data']) > 0:
                role = response_data['data'][0].get('role', 'Role not found')
                return role, bearer_token
        
        print(f"Error getting user role (Attempt {attempt + 1}/{MAX_RETRIES}):", response.status_code, response.text)
        time.sleep(2)  # Short delay before retrying
    
    print(f"Failed to get role for {email} after multiple attempts.")
    return None, bearer_token


def export_to_csv(data):
    with open("mimecast-user-with-role.csv", "w", newline='', encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["email", "role"])
        for user in data:
            if user['role'] != "na" and user['role'] != None and user['role'] != "":
                writer.writerow([user['email'], user['role']])


# Main execution
def main():
    bearer_token = get_bearer_token()
    
    if bearer_token:
        users, bearer_token = get_users(bearer_token)
        print(f"Total users fetched: {len(users)}")
        
        output = []
        for i, user in enumerate(users):
            if not user.get('alias'):
                email = user.get('emailAddress')
                if email and "@" in email:
                    print(f"Processing user {i+1}/{len(users)}: {email}")
                    role, bearer_token = get_user_role(email, bearer_token)
                    if role:
                        print(f"  Role: {role}")
                        output.append({"email": email, "role": role})
                    else:
                        print(f"  Failed to get role for {email}")
        
        if output:
            export_to_csv(output)
            print(f"Exported {len(output)} users with roles to CSV.")
        else:
            print("No user roles were found to export.")
    else:
        print("Failed to obtain bearer token.")


if __name__ == "__main__":
    main()
