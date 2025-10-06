from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO
import random
from string import ascii_uppercase



app = Flask(__name__)
##  Used to encrypt stuff
app.config["SECRET_KEY"] = "sdkfnlerjgsnd"
socketio = SocketIO(app)

g_rooms_codes: dict[str, dict[int, list]] = {}

def generate_unique_code(length: int) -> str:
    """
        So it generates a random code with the specified length from the
        uppercase ASCII characters.
        If the code is not inside the dictionary of codes mapping to unique rooms
        then it returns the code. 
    """
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)
        
        if code not in g_rooms_codes:
            break
    return code

@app.route("/", methods=["POST", "GET"])
def home_page():
    """
        The session is cleared when the user goes to the homepage
        is to prevent them from being able to go use the url routes
        to navigate -- so that once they're user details are deleted..
        if, for example, they try to go to the chat room, they will be
        redirected back to the homepage.
    """

    session.clear()
    if request.method == "POST":
        """
            Using request.form.get(<key_name>) is safer than request.form[<key_name>]
            as if the value doesn't exist, it gives type `None`.
            Also, a default value can be given to it, as the second parameter
        """
        entered_name: str = request.form.get(key="name")
        entered_room_code: str = request.form.get(key="room_code")
        join_btn_val: bool = request.form.get(key="join_room_btn", default=False)
        create_btn_val: bool = request.form.get(key="create_room_btn", default=False)
        
        ##  If name is None or it's empty
        if not entered_name:
            ##  Here an error variable is being passed; it's key is error_msg and its value
            ## is the message.
            return render_template("home_page.html", error_msg="Please enter a name.", name=entered_name, room_code=entered_room_code)

        ## there's no room code
        if join_btn_val != False and not entered_room_code:
            return render_template("home_page.html", error_msg="Please enter a room code.", name=entered_name, room_code=entered_room_code)

        """
            If they entered a room code, it has to be checked for whether it exists.
            If it does not exist, we handle it
        """
        room_code = entered_room_code

        ##  If they chose to create room
        if create_btn_val != False:
            ##  Re-assign the choice room
            ##  the 4 is the length
            room_code = generate_unique_code(4)
            g_rooms_codes[room_code] = {"members": 0, "messages": []}
        ##  They are joining a room but it's code does not exist.
        elif room_code not in g_rooms_codes:
            return render_template("home_page.html", error_msg="Room does not exist.", name=entered_name, room_code=entered_room_code)
        
        ##  Using Sessions to Store data!
        ##  They are semi-permanent!
        session["name"] = entered_name
        session["room_code"] = room_code
        
        ##  This is if the room entered was successful
        return redirect(url_for("room_page"))

    ##  Note that the arguments are
    return render_template("home_page.html")

@app.route("/room")
def room_page():
    room = session.get("room_code")
    """
        The below prevents one from directly going to the /room route by typing into the url.
        It only allows this if one successfully entered a name and room code
        that was valid.
    """
    if room is None or session.get("name") is None or room not in g_rooms_codes:
        return redirect(url_for("home_page")) 

    """
        Note that messages is sent to room_page.html as an argument
        It's sent as a list of the messages and their corresding sources
        In the .html, the flax-pypy code is used to loop through it
        and display the messages -- It's actually a django thing tho!
        Note that the messages are JSON format/python dictionary format
    """
    return render_template("room_page.html", room_code=room,
                           messages=g_rooms_codes[room]["messages"])

@socketio.on("message")
def message(data):
    room = session.get("room_code")
    if room not in g_rooms_codes:
        return
    
    """
        This is the place where it would have been ideal to store the date of the message
        for when it was actually sent, it would have been stored here.
    """
    content = {
        "name": session.get("name"),
        "message": data["data"]
    }

    send(content, to=room)
    ##  Stores a history of all messages -- though it's RAM storage
    g_rooms_codes[room]["messages"].append(content)
    print(f"{session.get("name")} said: {data['data']}")

@socketio.on("connect")
def connect(auth):
    """
        This is how to properly initialise the sockets
        Here the rooms written, their codes, are used to create flask-socketio
        rooms.
    """
    name = session.get("name")
    room = session.get("room_code")

    ##  Ensure that there is actually a room and name to prevent someone from entering
    ##  the socket without going through homepage, by entering the route into the url

    if not room or not name:
        return
    if room not in g_rooms_codes:
        leave_room(room)
        return

    join_room(room)

    ##  This is how to emit a message to every client in a psecific room
    send({"name": name, "message": "has entered the room"}, to=room)
    ##  Increment number of members
    g_rooms_codes[room]["members"] += 1
    print(f"{name} joined room {room}")

@socketio.on("disconnect")
def disconnect():
    """
        Pree how  when more than one person has joined a room
        if one member leaves the room, the room is not destroyed.
        But if there is no one in the room, it is destroyed.
    """
    name = session.get("name")
    room = session.get("room_code")

    ## If the room exists
    if room in g_rooms_codes:
        g_rooms_codes[room]["members"] -= 1

        ##  If everyone leaves, delete the rooms
        if g_rooms_codes[room]["members"] <= 0:
            del g_rooms_codes[room]

    send({"name": name, "message": "has left the room."}, to=room)
    print(f"{name} has left the room {room}")

    ##  If the room does not exist
    if room not in g_rooms_codes:
        print(f"Room {room} has been destroyed.")
    else:
        print(f"Room {room} is still alive.")




if __name__ == "__main__":
    socketio.run(app, debug=True)
