from dynatrace import init
init()

from travel_agent import agent_invocation, run_agent_with_task

def main():
    input_query = "Hi, can you tell me about Broadway shows in NYC today at 7pm?"
    result = agent_invocation(input_query)
    print("Basic Query Result:\n", result['result'])
    print("=================")

    task_description = "Research and recommend suitable travel destinations for someone looking for cowboy vibes, rodeos, and museums in New York city. Use web search to find current information about venues, events, and attractions."
    task_result = run_agent_with_task(task_description)
    print("Task-based Query Result:\n", task_result['result'])


if __name__ == "__main__":
    main()
