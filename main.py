import g4f
import flask
import requests
import datetime
import os

app = flask.Flask(__name__)

# Define system messages for each mode
system_messages = {
    "cat": os.getenv('cat'),
    "dog": os.getenv('dog'),
  "info": os.getenv('promptclone'),
  "normal": os.getenv('normal')
}

# Define rate limit function
def check_rate_limit(id):
    # Get current date and time
    now = datetime.datetime.now()
    # Get current minute and day
    current_minute = now.strftime("%Y-%m-%d %H:%M")
    current_day = now.strftime("%Y-%m-%d")
    # Initialize request count for minute and day
    request_count_minute = 0
    request_count_day = 0
    # Get request history from a file or database (not implemented here)
    request_history = []
    # Loop through request history
    for request in request_history:
        # Get request id, date and time
        request_id = request["id"]
        request_date = request["date"]
        request_time = request["time"]
        # If request id matches id parameter
        if request_id == id:
            # Increment request count for day
            request_count_day += 1
            # If request time matches current minute
            if request_time == current_minute:
                # Increment request count for minute
                request_count_minute += 1
    # If request count for minute exceeds 20 or request count for day exceeds 2000
    if request_count_minute > 20 or request_count_day > 2000:
        # Return True (rate limit exceeded)
        return True
    else:
        # Return False (rate limit not exceeded)
        return False

# Define route for api url
@app.route("/")
def api():
    # Get query, id, mode and internet from url parameters
    query = flask.request.args.get("msg")
    id = flask.request.args.get("id")
    mode = flask.request.args.get("mode")
    internet = flask.request.args.get("internet")
    # Print id to console
    print(id)
    # Check rate limit for id
    if check_rate_limit(id):
        # Return message with 200 status code saying rate limit exceeded
        return flask.jsonify({"message": "You have exceeded the rate limit. Please try again later."}), 200
    else:
        # Get system message for mode from dictionary using get method with a default value 
        system_message = system_messages.get(mode, "Invalid mode")
        # Get current date and time using datetime module 
        now = datetime.datetime.now()
        # Format date as weekday, day, month and year 
        date = now.strftime("%A, %d %B, %Y")
        # Format time as hour, minute and second 
        time = now.strftime("%I:%M:%S %p")
        # Check if internet parameter is set to on
        if internet == "on":
            # Send a GET request to the DuckDuckGo API endpoint with the query parameter as the query and limit the results to 5
            ddg_response = requests.get(f"https://ddg-api.herokuapp.com/search?query={query}")
            # Check if the response status code is OK 
            if ddg_response.ok:
                # Parse the ddg_response as a JSON object and store it in a variable called ddg_data
                ddg_data = ddg_response.json()
                # Create an empty list called formatted_data to store the formatted link and snippet strings
                formatted_data = []
                # Loop through each item in the ddg_data list and extract the link and snippet values
                for item in ddg_data:
                    link = item["link"]
                    snippet = item["snippet"]
                    # Use string formatting to create a string that follows the template "link: (the link), snippet: (the snippet)." for each item and append it to the formatted_data list
                    formatted_string = f"link: {link}, snippet: {snippet}."
                    formatted_data.append(formatted_string)
                # Join the formatted_data list with a space as a separator and store it in a variable called formatted_output
                formatted_output = " ".join(formatted_data)
                # Assign the formatted_output to a variable called internet_output 
                internet_output = formatted_output
                # Assign the date to a variable called current_date
                current_date = date
                # Assign the time to a variable called current_time
                current_time = time
                # Add the internet_output to the system_message with a colon and a space as separators
                system_message = system_message + ": " + internet_output + f"current date: {current_date}, current time: {current_time}"
            else
                # Print or return the response text to see what the response contains 
                print(ddg_response.text)
                # Return a message with 200 status code saying that the web scraping failed 
                return flask.jsonify({"message": "Web scraping failed. Please try again later."}), 200
        # Create list of messages with the modified system_message as the first element and the user's query as the second element
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": query}
        ]
        # Pass list of messages to g4f.ChatCompletion.create method with model as 'gpt-4' and provider as g4f.Provider.GetGpt
        response = g4f.ChatCompletion.create(model='gpt-3.5-turbo', provider=g4f.Provider.ChatgptAi, messages=messages)
        # Return response as json object with 200 status code
        return flask.make_response(response), 200

# Run app on port 5000 (default)
if __name__ == "__main__":
  app.run(host="0.0.0.0", port=3000)
