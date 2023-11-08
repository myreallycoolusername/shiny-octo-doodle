# Import all necessary packages
import g4f
from freeGPT import AsyncClient
import flask
from flask import Flask, request, send_file, render_template, abort, url_for, redirect
import requests
import asgiref
import uuid
import sentry_sdk
from flask_executor import Executor
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pymongo import MongoClient
import ipaddress
import datetime
import os
from duckduckgo_search import AsyncDDGS
from PIL import Image
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
from youtubesearchpython import *

sentry_sdk.init(
    dsn=os.getenv('SENTRYDSN'),
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    traces_sample_rate=1.0,
    # Set profiles_sample_rate to 1.0 to profile 100%
    # of sampled transactions.
    # We recommend adjusting this value in production.
    profiles_sample_rate=1.0,
)

app = Flask(__name__)

# Get the banned IPs (ip range) from the environment variable
ip_range = os.getenv("NETBAN")

# Convert the value to a Python list by splitting it by commas
ip_range = ip_range.split(",")

# Strip any whitespace from the IP ranges
ip_range = [ip.strip() for ip in ip_range]

# Convert the IP ranges to IPv4Network or IPv6Network objects
ip_range = [ipaddress.ip_network(ip) for ip in ip_range]

# Get the banned IPs (not ip range) from the environment variable
ip_ban = os.getenv("IPBAN")

# Split the banned IPs by commas and convert them to a set
ip_ban = set(ip_ban.split(","))

# Strip any whitespace from the IP addresses
ip_ban = [ip.strip() for ip in ip_ban]

executor = Executor(app)

# Define system messages for each mode
system_messages = {
    "cat": os.getenv('CAT_MODE'),
    "dog": os.getenv('DOG_MODE'),
    "info": os.getenv('I_MODE'),
    "normal": os.getenv('DEFAULT'),
    "img": os.getenv('VID_MODE'),
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
    default_limits=["30/minute", "1/second"],
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
@limiter.limit("10/minute;2000/day", key_func=lambda: request.args.get('id'))
def api():
    searches = []
    # Get query, id, mode and internet from url parameters using request.args dictionary 
    args = flask.request.args 
    query = args.get("msg")
    id = args.get("id")
    banned_ids = os.getenv('BANNEDIDS')
    banned_ids = banned_ids.split(',')
    if id in banned_ids:
        return 'sorry but you are banned lol  what did you even do to get banned bruh??  anyway, do you want some cookies? '
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
                async def search1():
                    async with AsyncDDGS(proxies=os.getenv('PROXY'), timeout=120) as ddgs:
                        for r in ddgs.text(query, max_results=50):
                            if type(r) == dict:
                                searches = [r]
                            else:
                                searches = r.json()
                                #hey! you found me! ;)
                searchesv = searches
                formatted_data = []
                for item in searchesv:
                    link = item["href"]
                    snippet = item["body"]
                    title = item["title"]
                    formatted_string = f"link: {link}, title: {title}, snippet: {snippet}. (... means there's more)"
                    formatted_data.append(formatted_string)

                formatted_output = " ".join(formatted_data)
                internet_output = formatted_output
                system_message = f"{system_message}: {internet_output}."

            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": query}
            ]
            proxy=os.getenv('PROXY2'),
            response = g4f.ChatCompletion.create(model='gpt-4', provider=g4f.Provider.Liaobots, messages=messages)
            return flask.make_response(response), 200
            run(search1())

@app.route('/transcript', methods=['GET'])
@limiter.limit("10/minute;1500/day", key_func=lambda: request.args.get('id'))
def transcript():
    searchsys = os.getenv('SEARCHSYS')
    searches = []
    system_message = []
    videoid = request.args.get('videoid')
    id = request.args.get('id')
    banned_ids = os.getenv('BANNEDIDS')
    banned_ids = banned_ids.split(',')
    if id in banned_ids:
        return 'sorry but you are banned lol  what did you even do to get banned bruh??  anyway, do you want some cookies? '
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
    try:
        transcript = YouTubeTranscriptApi.get_transcript(videoid)
        formatted_transcript = ". ".join([f"{caption['start']}s, {caption['text']}" for caption in transcript])
    except TranscriptsDisabled:
        print(f"Oops! Subtitles are disabled for this video. Video ID: {videoid}, ip of user: {visitor_ip}")
        transcript = f"Transcript for YouTube video with Video ID {videoid} is unavailable."
        formatted_transcript = "Sorry, transcript of video is unavailable. Use title or description or both as information!"
    
    video = Video.get(videoid, mode=ResultMode.json, get_upload_date=True)
    now = datetime.datetime.now()
    date = now.strftime("%A, %d %B, %Y")
    time = now.strftime("%I:%M:%S %p")
    title = video['title']
    secondsText = video['duration']['secondsText']
    viewCount = video['viewCount']['text']
    uploader = video['channel']['name']
    descr = video['description']
    link = video['link']
    formatted_vid_info = f'info of requested YouTube video: title of video: {title}, the duration of the video in seconds: {secondsText}, view count of video: {viewCount}, uploader of video: {uploader}, link of video: {link}'
    wholesearchsys = f"{searchsys}. Transcript: {formatted_transcript}. Info of YouTube video: title of video: {title}, description: {descr}."
    messages1 = [
        {"role": "system", "content": searchsys},
        {"role": "user", "content": wholesearchsys}
    ]
    proxy=os.getenv('PROXY2'),
    thingtosearch = g4f.ChatCompletion.create(model='gpt-3.5-turbo', provider=g4f.Provider.Llama2, messages=messages1)
    if internet == "on":
        async def search2():
            with AsyncDDGS(proxies=os.getenv('PROXY'), timeout=120) as ddgs:
                for r in ddgs.text(thingtosearch, max_results=3000000):
                    if type(r) == dict:
                        searches = [r]
                    else:
                        searches = r.json()
                        #awww cmon stop scrolling
        searchesv = searches
        formatted_data = []
        for item in searchesv:
            link = item["href"]
            snippet = item["body"]
            title = item["title"]
            formatted_string = f"link: {link}, title: {title}, snippet: {snippet}. (... means there's more)"
            formatted_data.append(formatted_string)

        formatted_output = " ".join(formatted_data)
        internet_output = formatted_output
        system_message = f"{system_message}: {internet_output}. transcript of video: {formatted_transcript}. info of video: {formatted_vid_info}"

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": query}
    ]
    proxy=os.getenv('PROXY2'),
    response = g4f.ChatCompletion.create(model='gpt-4', provider=g4f.Provider.Liaobots, messages=messages)
    return flask.make_response(response), 200
    run(search2())

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
    return render_template('homepage.html')

# The /generate endpoint for generating images
@app.route('/generate', methods=['GET'])
@limiter.limit("10 per minute;9000 per day", key_func=lambda: request.args.get('id'))
async def generate():
    id = request.args.get('id')
    banned_ids = os.getenv('BANNEDIDS')
    banned_ids = banned_ids.split(',')
    if id in banned_ids:
        return 'sorry but you are banned lol  what did you even do to get banned bruh??  anyway, do you want some cookies? '
    prompt = request.args.get('prompt')
    useragent = request.headers.get('user-agent')
    resp = await AsyncClient.create_generation("prodia", prompt)
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
    run(generate())

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
    # Convert the IP address to IPv4Address or IPv6Address object
    ip = ipaddress.ip_address(ip)
    # Loop through the list of banned ranges
    for range in ip_range:
        # If the IP address belongs to a banned range, abort the request with a 403 error and print the IP
        if ip in range:
            print(f"IP {ip} in banned range is banned from accessing the API but tried accessing the API")
            abort(403)
    # Loop through the list of banned addresses
    for address in ip_ban:
        # If the IP address matches a banned address, abort the request with a 403 error and print the IP
        if ip == address:
            print(f"IP {ip} is banned from accessing the API but tried accessing the API")
            abort(403)

@app.errorhandler(404)
# inbuilt function which takes error as parameter
def not_found(e):
    # defining function
    return render_template('404.html'), 404

@app.errorhandler(500)
# inbuilt function which takes error as parameter
def server_err(e):
    # defining function
    return render_template('500.html'), 500

@app.errorhandler(403)
# inbuilt function which takes error as parameter
def notallowed(e):
    # defining function
    return render_template('403.html'), 403

@app.errorhandler(429)
# inbuilt function which takes error as parameter
def limit(e):
    # defining function
    return render_template('429.html'), 429

def delete_image(filepath, delay):
    time.sleep(delay)
    if os.path.exists(filepath):
        os.remove(filepath)

# Run app on port 3000
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
