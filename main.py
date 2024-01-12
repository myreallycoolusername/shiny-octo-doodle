# Import all necessary packages
import g4f
import socket
from freeGPT import AsyncClient
import flask
from waitress import serve
from flask import Flask, request, send_file, render_template, abort, url_for, redirect, make_response, jsonify
import requests
import asgiref
from io import BytesIO
from asyncio import run
import uuid
import sentry_sdk
from flask_ipban import IpBan
from flask_executor import Executor
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pymongo import MongoClient
import ipaddress
from bs4 import BeautifulSoup
import urllib.parse
from bardapi import Bard
import datetime
import time
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

# Start Flask-IPBan
ipban = IpBan(ban_seconds=432000, ip_header='X-Forwarded-For')

# AbuseIPDB key
abipdbkey = os.getenv("ABUSEIPDBKEY")

# Load nuisances from Flask-IpBan
ipban.load_nuisances()

# Load AbuseIPDB from Flask-IpBan
ipban.abuse_IPDB_config = {'key': abipdbkey, 'report': True, 'load': False}

# Initiate Flask-IpBan
ipban.init_app(app)

# Whitelisted IPS
whitelistedips = os.getenv('WHITELISTEDIPS')

# Split whitelisted IPs
whitelistedips = set(whitelistedips.split(","))

# Strip whitespace from Whitelisted IPS
whitelistedips = [whitelisted.strip() for whitelisted in whitelistedips]

ipban.ip_whitelist_add(whitelistedips)

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

# Get banned IDS
banned_ids = os.getenv('BANNEDIDS')
banned_ids = banned_ids.split(',')

# Enable logging for g4f
g4f.debug.logging = True

# Get banned user agents
blocked_user_agents = os.getenv('UAGENT').split(',')

# Proxies for Bard
proxies = {
    'http': os.getenv("PROXY4"),
    'http': os.getenv("PROXY5"),
    'http': os.getenv("PROXY6"),
    'http': os.getenv("PROXY7")
}
# Load necessary things for Bard (TTS)
bardtoken = os.getenv('BARDCOOKIE')
bard = Bard(token=bardtoken, proxies=proxies)

executor = Executor(app)

# Define system messages for each mode
system_messages = {
    "cat": os.getenv('CAT_MODE'),
    "dog": os.getenv('DOG_MODE'),
    "info": os.getenv('I_MODE'),
    "normal": os.getenv('DEFAULT'),
    "img": os.getenv('VID_MODE'),
    "devmode": os.getenv('DEV_MODE'),
    "search": os.getenv('SEARCHSYS'),
    "searchchat": os.getenv('SEARCHCHATSYS'),
    "sumsys": os.getenv('SUMSYS')
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
# Fix url function
def fix_url(url):
    if not urllib.parse.urlparse(url).scheme:
        url = "https://" + url
    return url

# Delete a file function
def delete_file(file_path, delete_time):
    while time.time() < delete_time:
        time.sleep(1)
        if os.path.exists(file_path):
            os.remove(file_path)


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
@limiter.limit("100/minute;14400/day", key_func=lambda: request.args.get('id'))
async def chat():
    searchq = []
    messages = []
    dns_list = []
    searches = []
    searchsysc = []
    # Get query, id, mode and internet from url parameters using request.args dictionary 
    args = flask.request.args 
    query = args.get("msg", "Repeat after me: Sorry, there's nothing to respond! Here's a joke for you: (replace with your joke)")
    id = args.get("id", "1")
    if id in banned_ids:
        return 'sorry but you are banned lol (or you didnt specify your id, stranger!). lemme ask a question, what did you even do to get banned 🤨? im curious. anyway, do you want some cookies? 🍪'
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
        # grrrrr
    ip_list = visitor_ip.split(",")
    for ip in ip_list:
        try:
            dns = socket.gethostbyaddr(ip)[0]
        except socket.herror:
            dns = "No DNS found"
        except socket.gaierror:
            dns = "no dns found"
            dns_list.append(dns)
            dns = ",".join(dns_list)
    # Print the visitor IP to console
    print(f"Visitor IP on /chat: {visitor_ip} (dns: {dns}), useragent: {useragent}. Query: {query}")
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
            # Make query's value equal to a variable
            searchq = query
            # Get system message for searching
            searchsysc = system_messages.get("searchchat")
            # Search engine system prompt variable
            searchsysc = os.getenv('CHATSEARCHSYS')
            # Get current date and time using datetime module 
            now = datetime.datetime.now()
            # Format date as weekday, day, month and year 
            date = now.strftime("%A, %d %B, %Y")
            # Format time as hour, minute and second 
            time = now.strftime("%I:%M:%S %p")
            messages = [
                {"role": "system", "content": searchsysc},
                {"role": "user", "content": query}
            ]
            proxy=os.getenv('PROXY3'),
            searches = g4f.ChatCompletion.create(model=g4f.models.default, provider=g4f.Provider.Llama2, messages=messages)
            # Check if internet parameter is set to on
            if internet == "on":
                async def search1():
                    async with AsyncDDGS(proxies=os.getenv('PROXY'), timeout=120) as ddgs:
                        for r in ddgs.text(searches, region='wt-wt', safesearch=on, max_results=500000000000000000000000000000):
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
            response = g4f.ChatCompletion.create(model=g4f.models.default, provider=g4f.Provider.HuggingChat, messages=messages, cookies={"token": os.getenv('HFCOOKIE')}, auth=True)
            #return make_response(response), 200
            return jsonify({'answer': response}), 200
            run(search1())

@app.route('/transcript', methods=['GET'])
@limiter.limit("200/minute;28800/day", key_func=lambda: request.args.get('id'))
async def transcript():
    searchsys = system_messages.get("search")
    searches = []
    dns_list = []
    missing_params = []
    novparams = []
    messages1 = []
    messages = []
    system_message = []
    videoid = request.args.get('videoid', 'Empty')
    id = request.args.get('id', '1')
    if id in banned_ids:
        return 'sorry but you are banned lol (or you didnt specify your id, stranger!) heres a question: what did you even do to get banned? im curious 🤨. anyway, do you want some cookies? 🍪🍪'
    query = request.args.get('query', 'Empty')
    internet = request.args.get('search', 'off')
    useragent = request.headers.get("user-agent")
    if videoid == 'Empty':
        missing_params.append("videoid")
        if query == 'Empty':
            missing_params.append("query")
            if missing_params:
                return jsonify({'error': "You don't have the following parameter(s): " + ', '.join(missing_params)}), 400
            else:
                if videoid is None:
                    novparams.append("videoid")
                    if query is None:
                        novparams.append("query")
                        if id is None:
                            id = '1'
                            if novparams:
                                return jsonify({'error': "The following parameter(s) doesn't have a value: " + ', '.join(novparams)}), 400
                                #No!
    # Try to get the visitor IP address from the X-Forwarded-For header
    visitor_ip = request.headers.get("X-Forwarded-For")
    # If the header is None, try to get the visitor IP address from the True-Client-IP header
    if visitor_ip is None:
        visitor_ip = request.headers.get("True-Client-IP")
    # If the header is None, use the remote_addr attribute instead
    if visitor_ip is None:
        visitor_ip = request.remote_addr
        #😠😠😠
    ip_list = visitor_ip.split(",")
    for ip in ip_list:
        try:
            dns = socket.gethostbyaddr(ip)[0]
        except socket.herror:
            dns = "No DNS found"
        except socket.gaierror:
            dns = "no dns found"
            dns_list.append(dns)
            dns = ",".join(dns_list)
    # Print the visitor IP to console
    print(f"/transcript: id: {id} with ip {visitor_ip} (dns: {dns}) requested a query about a YouTube video with video id {videoid}, query: {query}. useragent: {useragent}")
    try:
        transcript = YouTubeTranscriptApi.get_transcript(videoid, proxies={"socks5": os.getenv('PROXYTR')})
        formatted_transcript = ". ".join([f"{caption['text']}" for caption in transcript])
    except TranscriptsDisabled:
        print(f"Oops! Subtitles are disabled for this video. Video ID: {videoid}, ip of user: {visitor_ip}")
        transcript = f"Sorry, transcript is unavailable."
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
    thingtosearch = g4f.ChatCompletion.create(model=g4f.models.default, provider=g4f.Provider.Llama2, messages=messages1)
    if internet == "on":
        async def search2():
            with AsyncDDGS(proxies=os.getenv('PROXY'), timeout=120) as ddgs:
                for r in ddgs.text(thingtosearch, region='wt-wt', safesearch=on, max_results=300000000000000):
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
        system_message = f"{system_message}. Internet Search Results: {internet_output}. transcript of video: {formatted_transcript}. info of video: {formatted_vid_info}. Today's date is: {date}, the current time is: {time}."

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": query}
    ]
    proxy=os.getenv('PROXY2'),
    response = g4f.ChatCompletion.create(model=g4f.models.default, provider=g4f.Provider.Huggingchat, messages=messages, cookies={"token": os.getenv('HFCOOKIE')}, auth=True)
    #return make_response(response), 200
    return jsonify({'answer': response}), 200
    run(search2())

# Default page
@app.route('/')
def home():
    useragent = request.headers.get("user-agent")
    otherw = request.args.get('other')
    funnyredirect = request.args.get('duck')
    dns_list = []
    urltoredirect = os.getenv('DYTLINK')
    name = os.getenv('NAME')
    # Try to get the visitor IP address from the X-Forwarded-For header
    visitor_ip = request.headers.get("X-Forwarded-For")
    # If the header is None, try to get the visitor IP address from the True-Client-IP header
    if visitor_ip is None:
        visitor_ip = request.headers.get("True-Client-IP")
    # If the header is None, use the remote_addr attribute instead
    if visitor_ip is None:
        visitor_ip = request.remote_addr
        #😠😠😠😠😠😰😰😰😰😰😰
    ip_list = visitor_ip.split(",")
    for ip in ip_list:
        try:
            dns = socket.gethostbyaddr(ip)[0]
        except socket.herror:
            dns = "No DNS found"
        except socket.gaierror:
            dns = "No DNS found"
            dns_list.append(dns)
            dns = ",".join(dns_list)
    # Print the visitor IP to console
    print(f"Visitor IP on homepage: {visitor_ip} (dns: {dns}) with useragent: {useragent}")
    if otherw == "true":
        return render_template('otherhome.html', n = name)
        #h
    if funnyredirect == "true":
        return redirect(urltoredirect, code=302)
        #stop 🚫🚫🚫
    else:
        return render_template('homepage.html')
        # shhhhhhh 🤫🤫🤫

@app.route("/sumurl", methods=["GET"])
@limiter.limit("30 per minute;90000 per day", key_func=lambda: request.args.get("id"))
async def urlsum():
   id = request.args.get("id", "1")
   if id in banned_ids:
       return jsonify({"error": "sorry but you are banned lol what did you even do to get banned bruh?? anyway, do you want some cookies? here --> 🍪🍪"})
   internet = request.args.get("internet", "off")
   query = request.args.get("msg", "Empty")
   useragent = request.headers.get("user-agent")
   searches = []
   novparams = []
   dns_list = []
   thingtosearch = []
   messages = []
   url = fix_url(request.args.get("url", "Empty"))
   system_message = system_messages.get("sumsys")

   if query == "Empty":
       novparams.append("query")
       if url == "Empty":
           novparams.append("url")
           if novparams:
               return jsonify({"error": "The following parameter(s) doesn't have a value: " + ", ".join(novparams)}), 400
           else:
               err = []
               if not id:
                  err.append("Id parameter is required. ")
               if not query:
                  err.append("Query parameter is required. ")
               if not url:
                  err.append("Url parameter is required. ")

               if len(err) > 0:
                  error_output = "".join(err)
                  return flask.make_response(flask.jsonify({"error": error_output}, 200))

   visitor_ip = request.headers.get("X-Forwarded-For")
   if visitor_ip is None:
       visitor_ip = request.headers.get("True-Client-IP")
   if visitor_ip is None:
       visitor_ip = request.remote_addr
   ip_list = visitor_ip.split(",")
   for ip in ip_list:
       try:
           dns = socket.gethostbyaddr(ip)[0]
       except socket.herror:
           dns = "No DNS found"
       except socket.gaierror:
           dns = "No DNS found"
       dns_list.append(dns)
   dns = ",".join(dns_list)
   print(f"Visitor IP on /sumurl: {visitor_ip}. ID: {id}, query: {query}.")
   proxy = {"socks5": os.getenv("PROXY1")}
   response = requests.get(url, proxies=proxy)
   soup = BeautifulSoup(response.content, "html.parser")
   links = soup.find_all("a")
   paragraphs = soup.find_all("p")
   text = soup.find_all("h2")
   scrapetext = (" ".join([p.get_text() for p in paragraphs]) + ". " + " ".join([link.get("href") for link in links]) + ". " + ", ".join([t.get_text() for t in text]) + ".")
   messages = [
       {"role": "system", "content": system_message},
       {"role": "user", "content": query},
   ]
   proxy = os.getenv("PROXY3")
   thingtosearch = g4f.ChatCompletion.create(
       model=g4f.models.default,
       provider=g4f.Provider.Llama2,
       messages=messages,
   )
   if internet == "on":
       async def search3():
           with AsyncDDGS(proxies=os.getenv("PROXY"), timeout=120) as ddgs:
               for r in ddgs.text(thingtosearch, region="wt-wt", safesearch=on, max_results=300000000000000):
                  if type(r) == dict:
                      searches = [r]
                  else:
                      searches = r.json()
                      searchesv = searches
                      formatted_data = []
                      for item in searchesv:
                          title = item["title"]
                          link = item["href"]
                          snippet = item["body"]
                          formatted_string = f"link: {link}, title: {title}, snippet: {snippet}. (... means there's more)"
                          formatted_data.append(formatted_string)
                      formatted_output = " ".join(formatted_data)
                      internet_output = formatted_output
                      if internet_output is None:
                          internet_output = "Internet disabled."
                      system_message = f"{system_message} Text:{scrapetext}. Internet Search Results: {internet_output}. Today's date is: {date}, the current time is: {time}."
   messages1 = [
       {"role": "system", "content": system_message},
       {"role": "user", "content": query},
   ]
   proxy = (os.getenv("PROXY2"),)
   finalresponse = g4f.ChatCompletion.create(model=g4f.models.default, provider=g4f.Provider.OnlineGpt, messages=messages)
   return jsonify({"answer": finalresponse}), 200

@app.route('/generate', methods=['GET'])
@limiter.limit("10 per minute;9000 per day", key_func=lambda: request.args.get('id'))
async def generate():
   id = request.args.get('id', '1')
   if id in banned_ids:
       return 'sorry but you are banned lol (or you didnt specify your id, stranger!) what did you even do to get banned? anyway, do you want some cookies? '
   prompt = request.args.get('prompt', 'Empty')
   dns_list = []
   useragent = request.headers.get('user-agent')
   novparams = []
   if prompt == 'Empty':
       return jsonify({'error': "You don't have the following parameter: prompt"}), 400
   else:
       if prompt is None:
           return jsonify({'error': "The following parameter is empty: prompt"}), 400
           if id is None:
               id = '1'
   try:
       resp = await AsyncClient.create_generation("prodia", prompt)
       img = Image.open(BytesIO(resp))
   except Exception as e:
       print('/generate: endpoint crashed. err: {e}')
       return f"we are very very very very very sowwy about this 😰😰😰😰😰 but our serwwers are not wurking 👉👈 maybe try again???? report to owner with this error: {e}"
   visitor_ip = request.headers.get("X-Forwarded-For")
   if visitor_ip is None:
       visitor_ip = request.headers.get("True-Client-IP")
   if visitor_ip is None:
       visitor_ip = request.remote_addr
   ip_list = visitor_ip.split(",")
   for ip in ip_list:
       try:
           dns = socket.gethostbyaddr(ip)[0]
       except socket.herror:
           dns = "No DNS found"
       except socket.gaierror:
           dns = "No DNS found"
       dns_list.append(dns)
       dns = ",".join(dns_list)
   print(f"Visitor IP on /generate: {visitor_ip} (dns: {dns}), and ID {id}, useragent: {useragent}. prompt: {prompt}")
   filename = f"{uuid.uuid1()}-DELETEDAFTER5MINS.png"
   os.makedirs('static', exist_ok=True)
   filepath = os.path.join('static', filename)
   img.save(filepath)
   executor.submit_stored('delete_file_' + filename, delete_file, file_path, time.time() + 300)
   return redirect(url_for('static', filename=filename))
   run(generate())

@app.route('/tts', methods=['GET'])
@limiter.limit("40 per minute;100000 per day", key_func=lambda: request.args.get('id'))
def tts():
  text = request.args.get('input', 'Empty')
  missing_params = []
  novparams = []
  dns_list = []
  id = request.args.get('id', 'Empty')
  if text == "Empty":
      missing_params.append("input")
      if id == "Empty":
          missing_params.append("id")
          if missing_params:
              return jsonify({'error': "You don't have the following parameter(s): " + ', '.join(missing_params)}), 400
          else:
              if text is None:
                novparams.append("input")
                if id is None:
                    novparams.append("id")
                    if novparams:
                        return jsonify({'error': "The following parameter(s) doesn't have a value: " + ', '.join(novparams)}), 400
  visitor_ip = request.headers.get("X-Forwarded-For")
  if visitor_ip is None:
      visitor_ip = request.headers.get("X-Real-IP")
      if visitor_ip is None:
          visitor_ip = request.headers.get("True-Client-IP")
          if visitor_ip is None:
              visitor_ip = request.remote_addr
  ip_list = visitor_ip.split(",")
  for ip in ip_list:
      try:
          dns = socket.gethostbyaddr(ip)[0]
      except socket.herror:
          dns = "No DNS found"
      except socket.gaierror:
          dns = "No DNS found"
  dns_list.append(dns)
  dns = ",".join(dns_list)
  print(f"Visitor IP on /tts: {visitor_ip} (dns: {dns}). tts prompt: {text}. id: {id}.")
  audio = bard.speech(text)
  filename = str(uuid.uuid1()) + ".mp3"
  file_path = os.path.join('static', filename)
  with open(file_path, "wb") as f:
      f.write(bytes(audio.get('audio', ''), encoding='utf-8'))
      executor.submit_stored('delete_file_' + filename, delete_file, file_path, time.time() + 300)
      return redirect(url_for('static', filename=filename)), 200


@app.route('/secretimgen', methods=['GET'])
@limiter.limit("-9999 per minute;-9999 per day", key_func=lambda: request.args.get('ign'))
async def genimgreserved():
    authpass = request.args.get('a')
    realpass = os.getenv('PASS')
    dns_list = []
    prompt = request.args.get('prompt')
    useragent = request.headers.get('user-agent')
    if authpass != realpass:
        abort(403)
        #im angry 😡😡😡😡😡😡
    try:
        resp = await AsyncClient.create_generation("prodia", prompt)
        img = Image.open(BytesIO(resp))
    except Exception as e:
        print(f"/secretimgen: error on endpoint, crashed. err: {e}")
        return f"we are soooooooooooooooooooo sorry about this 😭😭😭😭 please forgive us for this1!1!1!1! report this error to owner of this api: {e}"
        #ok im very very serious stop it now 😡
    # Try to get the visitor IP address from the X-Forwarded-For header
    visitor_ip = request.headers.get("X-Forwarded-For")
    # If the header is None, try to get the visitor IP address from the True-Client-IP header
    if visitor_ip is None:
        visitor_ip = request.headers.get("True-Client-IP")
    # If the header is None, use the remote_addr attribute instead
    if visitor_ip is None:
        visitor_ip = request.remote_addr
        # If visitor_ip is None, get the IP from X-Real_IP
    if visitor_ip is None:
        visitor_ip = request.headers.get("X-Real-IP")
        #Nothing more.
    ip_list = visitor_ip.split(",")
    for ip in ip_list:
        try:
            dns = socket.gethostbyaddr(ip)[0]
        except socket.herror:
            dns = "No DNS found"
        except socket.gaierror:
            dns = "No DNS found"
            dns_list.append(dns)
            dns = ",".join(dns_list)
    
    # Print the visitor IP to console
    print(f"IP on reserved genimg: {visitor_ip}, useragent: {useragent}")

    # Generate a random string for the filename
    filename = f"{uuid.uuid1()}-DELETEDAFTER5MINS.png"
    
    # Ensure the static folder exists
    os.makedirs('static', exist_ok=True)
    
    # Save the image to the static folder
    filepath = os.path.join('static', filename)
    img.save(filepath)

    # Schedule the deletion of the image file after 5 minutes
    executor.submit_stored('delete_file_' + filename, delete_file, file_path, time.time() + 300)

    # Redirect the user to the URL of the saved image
    return redirect(url_for('static', filename=filename))
    run(genimgreserved())



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
def check_ip(ip):
    ips = ip.split(',')
    for ip in ips:
        ip = ipaddress.ip_address(ip)
        # Perform the checks for each IP
        for range in ip_range:
            if ip in ipaddress.ip_network(range):
                print(f"IP {ip} in banned range is banned from accessing the API but tried accessing the API")
                abort(403)
                for address in ip_ban:
                    if ip == ipaddress.ip_address(address):
                        print(f"IP {ip} is banned from accessing the API but tried accessing the API")
                        abort(403)
                        def block_user_agents():
                            user_agent = request.headers.get('User-Agent')
                            if user_agent in blocked_user_agents:
                                abort(403)
                                # Fool me once, shame on you, fool me twice, shame on me, fool me thrice, shame on us!
@app.errorhandler(404)
# inbuilt function which takes error as parameter
def not_found(e):
    # defining function
    return render_template('404.html'), 404

@app.errorhandler(500)
# inbuilt function which takes error as parameter
def server_err(e):
    # defining function
    #return render_template('500.html'), 500
    return "oops, the server crashed lol, don't worry, it's not your fault. must be those rats in the servers room. 🐀🤬", 200

@app.errorhandler(403)
# inbuilt function which takes error as parameter
def notallowed(e):
    # defining function
    return render_template('403.html'), 403

@app.errorhandler(429)
# inbuilt function which takes error as parameter
def limit(e):
    # defining function
    #return render_template('429.html'), 429
    return "rate limit reached, try again later. wait, waittt, waitt... what did you even do to reach the rate limit?? 🤨🤨🤨🤨🤨🤨😳😳😳😳", 200
@app.errorhandler(502)
# inbuilt function which takes error as parameter
def idklewhatisthiserr(e):
    # defining function
    #return render_template('502.html'), 502
    return "uhmmm, so uhh this error got triggered because uhmmm there is no content to give you lol. they tell me im insane for writing these", 200


# Run app on port 3000
if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=3000) # use prod (?)
    #app.run(host="0.0.0.0", port=3000)
