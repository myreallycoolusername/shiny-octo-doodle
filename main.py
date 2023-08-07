import g4f
import flask
import requests
import datetime
import os
# Import Flask-Limiter and PyMongo 
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pymongo import MongoClient

app = flask.Flask(__name__)

# Define system messages for each mode
system_messages = {
    "cat": os.getenv('cat'),
    "dog": os.getenv('dog'),
  "info": os.getenv('promptclone'),
  "normal": os.getenv('normal'),
  "devmode": os.getenv('devmode')  
}

# Create a MongoClient instance and connect to MongoDB database 
client = MongoClient(os.getenv('mongodb'))
db = client.database

# Create a Limiter instance and pass it the get_remote_address function and the app instance 
limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri=os.getenv('mongodb'),
    default_limits=["2 per minute", "1 per second"],
    strategy="fixed-window"
)

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
# Use limiter.limit decorator to apply rate limits to api function 
@limiter.limit("10 per hour")
def api():
    # Get query, id, mode and internet from url parameters using request.args dictionary 
    args = flask.request.args 
    query = args.get("msg")
    id = args.get("id")
    mode = args.get("mode")
    internet = args.get("internet")
    # Print id to console
    print(id)
    # Check rate limit for id
    if check_rate_limit(id):
        # Return message with 200 status code saying rate limit exceeded
        return flask.jsonify({"message": "You have exceeded the rate limit. Please try again later."}), 200
    else:
        # Create an empty list to store error messages 
        errors = []
        # For each parameter, check if it is None or an empty string and append an error message to the errors list if so 
        if not query:
            errors.append("Query parameter is required.")
        if not id:
            errors.append("Id parameter is required.")
        if not mode:
            errors.append("Mode parameter is required.")
        if not internet:
            errors.append("Internet parameter is required.")
        # Check if errors list is empty or not using len function 
        if len(errors) > 0:
            # Join the errors list with a space as a separator and store it in a variable called error_output 
            error_output = " ".join(errors)
            # Return the error_output as a message with 400 status code (Bad Request) using flask.jsonify and flask.make_response functions 
            return flask.make_response(flask.jsonify({"message": error_output}), 400)
        else:
            # Get system message for mode from dictionary using get method with a default value 
            system_message = system_messages.get(mode, "h")
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
                    # System message
                    system_message = f"{system_message}: {internet_output}. current date: {current_date}. current time: {current_time}."
                else:
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
            response = g4f.ChatCompletion.create(model='gpt-4', provider=g4f.Provider.ChatgptAi, messages=messages)
            # Return response as json object with 200 status code
            return flask.make_response(response), 200

# Run app on port 5000 (default)
if __name__ == "__main__":
  app.run(host="0.0.0.0", port=3000)
