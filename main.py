import g4f
import flask
import requests
import datetime
import os

app = flask.Flask(__name__)

# Define system messages for each mode
system_messages = {
    "normal": "act like a normal chatbot that is cool and responds with emojis",
    "clone": os.getenv('promptclone')
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

# Define route for root path (homepage) (removed)


# Define route for api url
@app.route("/api")
def api():
    # Get query, id, and mode from url parameters
    query = flask.request.args.get("msg")
    id = flask.request.args.get("id")
    mode = flask.request.args.get("mode")
    # Print id to console
    print(id)
    # Check rate limit for id
    if check_rate_limit(id):
        # Return message with 200 status code saying rate limit exceeded
        return flask.jsonify({"message": "You have exceeded the rate limit. Please try again later."}), 200
    else:
        # Get system message for mode from dictionary
        system_message = system_messages[mode]
        # Create list of messages with system message as first element and user's query as second element
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": query}
        ]
        # Pass list of messages to g4f.ChatCompletion.create method with model as 'gpt-4' and provider as g4f.Provider.GetGpt
        response = g4f.ChatCompletion.create(model='gpt-4', provider=g4f.Provider.ChatgptAi, messages=messages)
        # Return response as json object with 200 status code
        return flask.make_response(response), 200

# Run app on 0.0.0.0 with port 3000 
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
