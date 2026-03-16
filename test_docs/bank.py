prompt = input("type a greeting ").strip().casefold()
if prompt.startswith("hello"):
    print("$0")
elif prompt.startswith("h"):
    if prompt != "hello":
        print("$20")
else:
    print("$100")
