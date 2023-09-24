import g4f
import freeGPT
import flask
from flask import Flask, request, send_file
from flask_ipblock import IPBlock
from flask_ipblock.documents import IPNetwork
import requests
import asgiref
from mongoengine import connect
import uuid
from flask_executor import Executor
import datetime
import os
from PIL import Image
from youtube_transcript_api import YouTubeTranscriptApi
# Import Flask-Limiter and PyMongo.
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pymongo import MongoClient
from io import BytesIO

connect(host=os.getenv('MONGODB2'))

# Get the banned IPs (not ip range) from the environment variable
ipban = os.getenv("IPBAN")

# Split the banned IPs by commas and convert them to a set
ipban = set(ipban.split(","))

# Strip any whitespace from the IP addresses
ipban = [ip.strip() for ip in ipban]

executor = Executor(app)

# Set up IPBlock
ipblock = IPBlock(app)

# Get the banned IPs (ip range) from the environment variable
netban = os.getenv("NETBAN")

# Split the banned IPs by commas and convert them to a set
netban = set(netban.split(","))

# Strip any whitespace from the IP addresses
netban = [ip.strip() for ip in netban]

# Create a MongoEngine document corresponding to a range of IP addresses
IPNetwork.objects.create_from_string(netban, label='spite')

# Define system messages for each mode
system_messages = {
    "cat": os.getenv('CAT_MODE'),
    "dog": os.getenv('DOG_MODE'),
  "info": os.getenv('I_MODE'),
  "normal": os.getenv('DEFAULT'),
  "devmode": os.getenv('DEV_MODE')  
}

# Create a MongoClient instance and connect to MongoDB database 
client = MongoClient(os.getenv('MONGODB'))
db = client.database

# Create a Limiter instance and pass it the get_remote_address function and the app instance 
limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri=os.getenv('MONGODB'),
    default_limits=["30 per minute", "1 per second"],
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
@app.route("/chat")
# Use limiter.limit decorator to apply rate limits to api function 
@limiter.limit("10 per minute;2000 per day", key_func=lambda: request.args.get('id'))
def api():
    # Get query, id, mode and internet from url parameters using request.args dictionary 
    args = flask.request.args 
    query = args.get("msg")
    id = args.get("id")
    mode = args.get("mode")
    internet = args.get("internet")
    useragent = request.headers.get("user-agent")
    # Try to get the visitor IP address from the X-Forwarded-For header
    visitor_ip = request.headers.get("X-Forwarded-For")
    # If the header is None, try to get the visitor IP address from the True-Client-IP header
    if visitor_ip is None:
        visitor_ip = request.headers.get("True-Client-IP")
    # If the header is None, use the remote_addr attribute instead
    if visitor_ip is None:
        visitor_ip = request.remote_addr
    # Print the visitor IP to console
    print(f"Visitor IP on /chat: {visitor_ip}, useragent: {useragent}")
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
            # Return the error_output as a message with 400 status code (Bad Request) using flask.jsonify and flask.make_response functions (changed) 
            return flask.make_response(flask.jsonify({"message": error_output}), 200)
        else:
            # Get system message for mode from dictionary using get method with a default value 
            system_message = system_messages.get(mode, "normal")
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
            response = g4f.ChatCompletion.create(model='gpt-4', provider=g4f.Provider.ChatBase, messages=messages)
            # Return response as json object with 200 status code
            return flask.make_response(response), 200
@app.route('/transcript', methods=['GET'])
@limiter.limit("10 per minute;1500 per day", key_func=lambda: request.args.get('id'))
def transcript():
    videoid = request.args.get('videoid')
    id = request.args.get('id')
    query = request.args.get('query')
    internet = request.args.get('search')
    useragent = request.headers.get("user-agent")
    # Try to get the visitor IP address from the X-Forwarded-For header
    visitor_ip = request.headers.get("X-Forwarded-For")
    # If the header is None, try to get the visitor IP address from the True-Client-IP header
    if visitor_ip is None:
        visitor_ip = request.headers.get("True-Client-IP")
    # If the header is None, use the remote_addr attribute instead
    if visitor_ip is None:
        visitor_ip = request.remote_addr
    # Print the visitor IP to console
    print(f"/transcript: id: {id} with ip {visitor_ip} requested a query about a YouTube video with video id {videoid}. useragent: {useragent}")
    transcript = YouTubeTranscriptApi.get_transcript(videoid)
    formatted_transcript = ". ".join([f"{caption['start']}s, {caption['text']}" for caption in transcript])
    system_message = os.getenv('V_MODE')

    now = datetime.datetime.now()
    date = now.strftime("%A, %d %B, %Y")
    time = now.strftime("%I:%M:%S %p")

    if internet == "on":
        ddg_response = requests.get(f"https://ddg-api.herokuapp.com/search?query={query}")
        if ddg_response.ok:
            ddg_data = ddg_response.json()
            formatted_data = []
            for item in ddg_data:
                link = item["link"]
                snippet = item["snippet"]
                formatted_string = f"link: {link}, snippet: {snippet}."
                formatted_data.append(formatted_string)
            formatted_output = " ".join(formatted_data)
            internet_output = formatted_output 
            current_date = date
            current_time = time
            system_message = f"{system_message}: {internet_output}. current date: {current_date}. current time: {current_time}. video's transcript: {formatted_transcript}."
        else:
            print(ddg_response.text)
            return flask.jsonify({"message": "Web scraping failed. Please try again later. Problem probably caused by the internet api."}), 200

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": query}
    ]
    response = g4f.ChatCompletion.create(model='gpt-4', provider=g4f.Provider.ChatBase, messages=messages)
    return flask.make_response(response), 200
# Default page
@app.route('/')
def home():
    useragent = request.headers.get("user-agent")
    # Try to get the visitor IP address from the X-Forwarded-For header
    visitor_ip = request.headers.get("X-Forwarded-For")
    # If the header is None, try to get the visitor IP address from the True-Client-IP header
    if visitor_ip is None:
        visitor_ip = request.headers.get("True-Client-IP")
    # If the header is None, use the remote_addr attribute instead
    if visitor_ip is None:
        visitor_ip = request.remote_addr
    # Print the visitor IP to console
    print(f"Visitor IP on homepage: {visitor_ip} with useragent: {useragent}")
    return 'hello hoomans. welcome to my super duper awesome api in flask! ;)\nhow to use api coming soon™.'
# The /generate endpoint for generating images
@app.route('/generate', methods=['GET'])
@limiter.limit("10 per minute;9000 per day", key_func=lambda: request.args.get('id'))
async def generate():
    id = request.args.get('id')
    prompt = request.args.get('prompt')
    useragent = request.headers.get('user-agent')
    resp = await getattr(freeGPT, "prodia").Generation().create(prompt)
    img = Image.open(BytesIO(resp))
    # Try to get the visitor IP address from the X-Forwarded-For header
    visitor_ip = request.headers.get("X-Forwarded-For")
    # If the header is None, try to get the visitor IP address from the True-Client-IP header
    if visitor_ip is None:
        visitor_ip = request.headers.get("True-Client-IP")
    # If the header is None, use the remote_addr attribute instead
    if visitor_ip is None:
        visitor_ip = request.remote_addr
    # Print the visitor IP to console
    print(f"Visitor IP on /generate: {visitor_ip} and ID {id}, useragent: {useragent}")

    
    # Generate a random string for the filename
    filename = f"{uuid.uuid4()}.png"
    
    # Ensure the static folder exists
    os.makedirs('static', exist_ok=True)
    
    # Save the image to the static folder
    filepath = os.path.join('static', filename)
    img.save(filepath)

    # Schedule the deletion of the image file after 5 minutes
    executor.submit(delete_image, filepath, delay=300)

    # Redirect the user to the URL of the saved image
    return redirect(url_for('static', filename=filename))

# Define a function to check the IP before each request
@app.before_request
def check_ip():
  # Get the IP from the X-Forwarded-For header
  ip = request.headers.get("X-Forwarded-For")
  # If the header is None, get the IP from the X-Real-IP header
  if ip is None:
    ip = request.headers.get("X-Real-IP")
  # If the IP is still None, get the IP from the request.remote_addr attribute
  if ip is None:
    ip = request.remote_addr
  # If the IP is in the list of banned IPs, abort the request with a 403 error
  if ip in ipban:
    print(f"IP {ip} is banned from accessing the API but tried accessing the API")  
    abort(403)

def delete_image(filepath, delay):
    time.sleep(delay)
    if os.path.exists(filepath):
        os.remove(filepath)

# Run app on port 5000 (default)
if __name__ == "__main__":
  app.run(host="0.0.0.0", port=3000)
