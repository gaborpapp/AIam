import pickle

def save(data, filename):
    print("saving %s..." % filename)
    f = open(filename, "wb")
    pickle.dump(data, f)
    f.close()
    print("ok")

def load(filename):
    print("loading %s..." % filename)
    f = open(filename, "rb")
    data = pickle.load(f)
    f.close()
    print("ok")
    return data
