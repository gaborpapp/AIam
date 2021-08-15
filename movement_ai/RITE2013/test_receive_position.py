import liblo

def receive_position(path, args, types, src, user_data):
    print(path, args)
    
server =  liblo.Server(7892, liblo.UDP)
server.add_method("/position", "ssf", receive_position)
while True:
    server.recv(100)
