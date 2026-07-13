from dynatrace import init
init()

from travel_agent import agent_invocation

def main():
    input_query = "Hi, can you tell me about Broadway shows in NYC today at 7pm?"
    result = agent_invocation(input_query)
    print("Result:\n", result['result'])


if __name__ == "__main__":
    main()
