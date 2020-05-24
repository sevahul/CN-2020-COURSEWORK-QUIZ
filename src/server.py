import operator
import socket
import select
import time


#defining data for the quiz
questions = [("What is the world’s most heavy land mammal?",
              "Hippopotamus", ["Hippopotamus", "Elephant", "Giraffe", "Gaur"]),
             ('Which Middle Eastern city is also the name of a type of artichoke',
              'Jerusalem', ["Jerusalem", "Istanbul", "Tehran", "Dubai"]),
             ('The Velocipede was a nineteenth-century prototype of what?',
              'a Bicycle', ["a Plane", "a Boat", "a Car", "a Bicycle"])]
TIME_FOR_QUESTION = 10

quiz_started = False

#defining protoclols parameters

HEADER_LENGTH = 10
exit_commands = ("close", "exit", "quit")
msg_types = {
    "j": "Username", #Information about the username immediately after connecting to the server
    "c": "command", #command for the server. Available commands: start
    "i": "inform", #inform clients about quiz start or end
    "q": "question", # ask question during the quiz
    "a": "answer", # send answer for the question
    "w": "winner", # announce the winner
    "e": "exit", # cancel the connection
    "o": "other", # other type. Temporary type to adopt previous version
    "W": "Winner" #announcing winner of the round
    }


def cr_header(str, msg_type):
    assert len(msg_type) == 1
    return f"{len(str):<{HEADER_LENGTH}}".encode() + msg_type.encode()
def cr_msg(msg, msg_type = "o"):
    return cr_header(msg, msg_type) + msg.encode()
def receive_msg(socket):
    try:
        msg_header = socket.recv(HEADER_LENGTH).decode()
        if msg_header == "":
            return ("", "e") # connection is closed
        msg_len = int(msg_header)
        msg_type = socket.recv(1).decode()
        msg = socket.recv(msg_len).decode()
        answ = (msg, msg_type)
        print(f"\t\t\tReceived msg: {msg}. type: {msg_type}")
        return answ
    except:
        return ("", "continue")

def accept_client(socket, sockets_list, clients):
    client_socket, client_address = socket.accept()
    user, type = receive_msg(client_socket)
    if type != "j":
        print(f"Connecting failed: type '{type}' insted of 'j' in header" )
        return False
    if user is False:
        return False
    sockets_list.append(client_socket)
    clients[client_socket] = user
    print((f"Accepted new connectinon from {client_address[0]} : {client_address[1]}",
           f'{user}'))
    return True

def assert_type(expected, real, user, msg):
    if real != expected:
        print(f"Unexpected msg type '{real}' ('{expected}' expected) \n"
              f"from {user} with payload {msg}. ")
        return False
    return True

def closed_connection(notified_socket, sockets_list, clients, user):
    print(f'Closed connection from {user}')
    sockets_list.remove(notified_socket)
    del clients[notified_socket]

def broadcast(msg, clients, msg_type="o"):
    for client in clients.keys():
        try:
            client.send(cr_msg(msg, msg_type))
        except:
            closed_connection(client, sockets_list, clients, user + " (exception socket)")

    print(f'Broadcasting message "{msg}" type "{msg_type}"' )
def send(msg, client, msg_type="o"):
    try:
        client.send(cr_msg(msg, msg_type))
    except:
        print(f'Failed to send message "{msg}" type "{msg_type}" to {clients[client]}')
        closed_connection(client, sockets_list, clients, user + " (exception socket)")
    print(f'Sent message "{msg}" type "{msg_type}" to {clients[client]}' )

def gen_quest(q):
    quest = cr_msg(q[0], "q").decode()
    answs = [cr_msg(i, "a").decode() for i in q[2]]
    res = quest
    for i in answs:
        res += i
    return res

#defining data for TCP and IP protocols
IP = "127.0.0.1"
PORT = 1234

server_soket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_soket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # allowing trying to connect to the port several times

#connecting to the port and starting listening to it
server_soket.bind((IP, PORT))
server_soket.listen()

#storing all the sockets
sockets_list = [server_soket]
clients = {}




status = "wait"

run = True
while run: #main loop
    print("Accepting all connections and listening to the commands...")

    quiz_started = False
    while not quiz_started: #accepting all connections and listening to the commands
        read_sockets, _, exception_sockets = select.select(sockets_list, [], sockets_list)
        for notified_socket in read_sockets:
            if notified_socket == server_soket: # accepting connection
                if not accept_client(server_soket, sockets_list, clients):
                    print(f"Error with connecting client")
            else: #listening to the commands
                msg, type = receive_msg(notified_socket)
                user = clients[notified_socket]
                if type == "e": #connection closed
                    closed_connection(notified_socket, sockets_list, clients, user)
                    continue
                if type == "continue" or quiz_started:
                    continue

                if not assert_type('c', type, user, msg):
                    continue

                #print(f"Received command from {user}: {msg}")
                if msg == "start":
                    quiz_started = True
                    broadcast("start", clients, "i")
                    print("THE QUIZ IS STARTED")
                    time.sleep(1)

        for notified_socket in exception_sockets:
            closed_connection(notified_socket, sockets_list, clients, user + " (exception socket)")
    countScore = {clientName:0 for clientName in clients.values()}
    quiz_clients = clients.copy()
    for q in questions:
        winner = "Friendship"
        print(f"Asking the question: {q}")
        broadcast(gen_quest(q), quiz_clients, "q")
        t = time.time()

        #listening to the answers
        correct_answer_recieved = False
        while time.time() - t < TIME_FOR_QUESTION and not correct_answer_recieved: # collecting the answers
            # import pdb
            # pdb.set_trace()
            read_sockets, _, exception_sockets = select.select(sockets_list, [], sockets_list, 0)
            for notified_socket in read_sockets:

                if notified_socket == server_soket: #accepting new connection
                    if not accept_client(server_soket, sockets_list, clients):
                        print(f"Error with connecting client")
                else:
                    answ, type = receive_msg(notified_socket)
                    user = clients[notified_socket]
                    if type == "e":
                        closed_connection(notified_socket, sockets_list, clients, user)
                        continue
                    if type == "continue":
                        continue
                    if type == "c" and answ == "start":
                        quiz_clients[notified_socket] = clients[notified_socket]
                        send("already", notified_socket, "i")
                        send(gen_quest(q), notified_socket, "q")
                    if not assert_type('a', type, user, answ):
                        continue

                    print(f"Received an answer from {user}: {answ} on {int(time.time() - t)} seconds")
                    if correct_answer_recieved:
                        print("But correct answer already received")
                    if  answ == q[1]:
                        # import pdb
                        # pdb.set_trace()
                        print("And that's right")
                        correct_answer_recieved = True
                        countScore[user] = countScore[user] + 1
                        winner = user
                    else:
                        print("And it's wrong!")

            for notified_socket in exception_sockets:
                closed_connection(notified_socket, sockets_list, clients, user + " (exception socket)")

        #announcing the winner
        broadcast(winner, quiz_clients, "w")
        print(f"time: {time.time() - t} ")
        time.sleep(2)
    broadcast("end", clients, "i")
    overall_winner = max(countScore.items(), key=operator.itemgetter(1))[0]
    max_score = max(countScore.items(), key=operator.itemgetter(1))[1]
    number_of_winners = sum([int(v==max_score) for _,v in countScore.items()])
    if number_of_winners > 1:
        overall_winner = "Friendship"
    else:
        overall_winner += " with " + str(max_score) + " Scores "

    broadcast(overall_winner, clients, "W")

def process_income():
    global status
    global correct_answer_recieved
    global winner
    global sockets_list
    global clients
    read_sockets, exception_sockets = None, None
    if status == "wait":
        global read_sockets, exception_sockets
        read_sockets, _, exception_sockets = select.select(sockets_list, [], sockets_list)
    elif status == "quiz":
        global read_sockets, exception_sockets
        read_sockets, _, exception_sockets = select.select(sockets_list, [], sockets_list, 0)
    else:
        print("Status error!")
    for notified_socket in read_sockets:

        if notified_socket == server_soket:  # accepting new connection
            if not accept_client(server_soket, sockets_list, clients):
                print(f"Error with connecting client")
        else:
            answ, type = receive_msg(notified_socket)
            user = clients[notified_socket]
            if type == "e":
                closed_connection(notified_socket, sockets_list, clients, user)
                return
            if type == "continue":
                return
            if type == "c" and answ == "start":
                if status == "wait":
                    broadcast("start", clients, "i")
                    broadcast(gen_quest(q), clients, "q")
                    status = "quiz"
                    return
                if status == "quiz":
                    send("start", notified_socket, "i")
                    send(gen_quest(q), notified_socket, "q")
                    return


            if type == "a":
                if status == "wait":
                    send("gotowait", notified_socket, "o")
                    return
                elif status == "quiz":
                    print(f"Received an answer from {user}: {answ} on {int(time.time() - t)} seconds")
                    if correct_answer_recieved:
                        print("But correct answer already received")
                        return
                    if answ == q[1]:
                        print("And that's right")
                        correct_answer_recieved = True
                        countScore[user] = countScore[user] + 1
                        winner = user
                        return
                    else:
                        print("And it's wrong!")
                        return
                else:
                    print("Status error")
                    return
            print(f"Unrecognized income type: {type}, msg: {msg}")



    for notified_socket in exception_sockets:
        closed_connection(notified_socket, sockets_list, clients, user + " (exception socket)")


