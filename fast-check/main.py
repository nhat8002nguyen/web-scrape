from openai import OpenAI
import os
import dotenv


def main():
    client = OpenAI(api_key=os.environ["OPENAI_KEY"])

    prompt = "Write a short story about a dog who goes on an adventure."

    response = client.completions.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt
    )

    print(response.choices[0].text)


if __name__ == "__main__":
    main()
