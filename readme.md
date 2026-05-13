To get the app running, you need python 3.14 installed, run "py -m pip install -r requirements.txt" and 
and you need an api key to put inside the .env you need to create\
e.g. HENRIK_API_KEY=HDEV-39...\
also you need to create an external database using "supabase.com". its completely free
create an account or use your github login and just keep all the settings the same. 
then if you're on the main screen, click on connect at the top, select session spooler and copy the 
link it provides below. replace [YOUR-PASSWORD] with your actual password you chose for the db
and add the whole database link in your .env file.\
e.g. DATABASE_URL=postgresql://postgres...\
to add players to your database, do the command "py -m main add-player <playername> <tagline>"
then start the app with the command "py -m ui.app" or just run the "launch.vbs" file and sync the stats
make sure you are inside the StatsAppPremier folder when executing any of the commands\

# Commands:
ignore seasons\
py -m main.py ignore-season <season_id>

include seasons\
py -m main.py include-season <season_id>

list ignored seasons\
py -m main.py ignored-seasons

display all seasons\
py -m main.py seasons

add players to tracking\
py -m main.py add-player <player_name> <tagline>