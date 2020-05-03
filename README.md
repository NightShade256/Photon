# Photon

A multipurpose Discord bot written in Python that is easy-to-use and fast.

## Setup

Photon can be self hosted on any platform of your choice.

### Windows and Linux

1. Install Python 3.8 or higher, Java 11, PostgreSQL server 12.

2. Create the a user and a database in PostgreSQL:

   ```SQL
   CREATE ROLE photonuser WITH LOGIN PASSWORD 'youshallnotpass';
   CREATE DATABASE photon OWNER photonuser;
   ```

3. Download and setup [Lavalink](https://github.com/Frederikam/Lavalink#server-configuration). Don't run lavalink just now, do it at a later stage.

4. Make a file called `config.py` in the root directory of the bot with the format:

    ```python
    core = {
        "token": "BOT TOKEN",
        "postgres_dsn": "postgres://user:pass@host:port/databasename"
    }

    nodes = {
        1: {
            "host": "127.0.0.1",
            "port": 2333,
            "rest_uri": "http://127.0.0.1:2333",
            "password": "youshallnotpass",
            "identifier": "Node-1",
            "region": "india"
        }
    }
    ```

    Change the values wherever necessary.

5. Install the bot dependencies:

    Windows: `pip install -r requirements.txt` in a CMD with elevated privileges.  
    Linux: `sudo pip3 install -r requirements.txt`

6. Run the Lavalink server by using:

    `java -jar lavalink.jar`

    Replace `lavalink.jar` with the actual filename.

7. Run the bot by doing:

    Windows: `python launcher.py`  
    Linux: `python3 launcher.py`

    You will see in the terminal window a message that confirms Photon is ready and has connected to
    the Lavalink server through websockets. If you see any error message check if you followed all the
    listed steps correctly. If the error still persists you can [contact me](#support) through Discord itself.

## Changelog

### v1.0a

1. Initial Release

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

Photon is licensed under the MIT License.

## Acknowledgements

1. The [GNU Unifont](https://savannah.gnu.org/projects/unifont) is used in this project.

2. The Music cog used in this bot is a heavily modified version of the Wavelink example cogs, which you can find [here](https://github.com/PythonistaGuild/Wavelink/tree/master/examples)

3. A few snippets of code were used from the RoboDanny project by Rapptz, which can be found [here](https://github.com/Rapptz/RoboDanny)

4. The Welcome and Goodbye base images are taken from the [Gearz](https://github.com/TheDiscordians/Gearz) bot (now defunct), with permission from the author of the bot.

## Support

Please feel free to contact me on Discord, if you have any query regarding Photon.
Username: `__NightShade256__#5169`
