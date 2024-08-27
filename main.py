import streamlit as st
import random
from PIL import Image
from streamlit_option_menu import option_menu
import requests
from urllib.parse import urlparse, parse_qs
import time

# Set the page configuration
st.set_page_config(page_title="Destiny 2 Manager", layout="wide")

# Main app title
st.title("D2Bunker")

modes = option_menu(
    menu_title=None,
    options=['Weapons', 'Subclass'],
    menu_icon='cast',
    default_index=0,
    orientation='horizontal',
)

if modes == 'Weapons':

    # Replace with your Bungie API key
    BUNGIE_API_KEY = "a2b3a3c648cb43a987e17a39a969cd32"

    # Bungie OAuth details
    CLIENT_ID = "48121"
    CLIENT_SECRET = "WXmzsnefGIWeyAaYWE383Qfs6R0P370cGW0qMtnXquI"
    REDIRECT_URI = "https://r3bunker.github.io/callback.html"

    # OAuth flow
    def get_access_token():
        if "access_token" not in st.session_state:
            code = st.query_params.get("code")
            
            if code:
                # Exchange the code for an access token
                data = {
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "redirect_uri": REDIRECT_URI
                }
                response = requests.post("https://www.bungie.net/platform/app/oauth/token/", data=data)
                if response.status_code == 200:
                    st.session_state["access_token"] = response.json()["access_token"]
                    st.success("Authentication successful!")
                    time.sleep(2)  # Give user time to see the success message
                    st.query_params.clear()  # Clear the code from the URL
                    st.rerun()
                else:
                    st.error(f"Failed to obtain access token. Status code: {response.status_code}")
                    st.json(response.json())
            else:
                # If we don't have a code, provide the authentication link
                oauth_url = f"https://www.bungie.net/en/OAuth/Authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}"
                st.markdown("### Authentication Required")
                st.markdown(f"[Click here to authenticate with Bungie]({oauth_url})")
                st.markdown("After authentication, you will be redirected back to this app automatically.")
            
            return None
        return st.session_state["access_token"]

    # Get user's Destiny 2 profile and character equipment
    def get_profile_and_equipment(access_token):
        headers = {
            "X-API-Key": BUNGIE_API_KEY,
            "Authorization": f"Bearer {access_token}"
        }
        response = requests.get("https://www.bungie.net/Platform/User/GetMembershipsForCurrentUser/", headers=headers)
        if response.status_code != 200:
            st.error(f"Failed to retrieve user profile. Status code: {response.status_code}")
            st.json(response.json())
            st.session_state.pop("access_token", None)
            st.rerun()
        
        membership_data = response.json()["Response"]["destinyMemberships"][0]
        membership_type = membership_data["membershipType"]
        membership_id = membership_data["membershipId"]
        
        profile_response = requests.get(f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Profile/{membership_id}/?components=100,102,200,201,205,300,301,304,305,306,307,308,310", headers=headers)
        if profile_response.status_code != 200:
            st.error(f"Failed to retrieve character data. Status code: {profile_response.status_code}")
            st.json(profile_response.json())
            return None, None, None, None, None
        
        try:
            profile_data = profile_response.json()["Response"]
            characters = profile_data.get("characters", {}).get("data", {})
            character_equipment = profile_data.get("characterEquipment", {}).get("data", {})
            vault_data = profile_data.get("profileInventory", {}).get("data", {}).get("items", [])
            
            return characters, character_equipment, vault_data, membership_type, membership_id
        except KeyError as e:
            st.error(f"Unexpected data structure in API response: {e}")
            return None, None, None, None, None

    # Fetch item details
    @st.cache_resource
    def get_item_details(item_hash):
        headers = {"X-API-Key": BUNGIE_API_KEY}
        response = requests.get(f"https://www.bungie.net/Platform/Destiny2/Manifest/DestinyInventoryItemDefinition/{item_hash}/", headers=headers)
        if response.status_code == 200:
            return response.json()["Response"]
        return None

    # Convert class type to string
    def get_class_name(class_type):
        class_names = {0: "Titan", 1: "Hunter", 2: "Warlock"}
        return class_names.get(class_type, "Unknown")

    def get_random_weapon(vault_data, slot_hash, ammo_type=None):
        # st.write(f"Total items in vault: {len(vault_data)}")

        # Filter for weapons only
        weapons = [item for item in vault_data if get_item_details(item['itemHash']).get('itemType') == 3]
        # st.write(f"Total weapons in vault: {len(weapons)}")

        # Filter weapons by slot
        slot_weapons = [weapon for weapon in weapons if get_item_details(weapon['itemHash'])['inventory']['bucketTypeHash'] == slot_hash]
        # st.write(f"Weapons in slot {slot_hash}: {len(slot_weapons)}")

        # Debug: Print some weapon details for the specific slot
        for i, weapon in enumerate(slot_weapons[:5]):  # Print details of first 5 weapons in the slot
            weapon_details = get_item_details(weapon['itemHash'])
            # st.write(f"Slot Weapon {i+1}: {weapon_details['displayProperties']['name']}, "
            #          f"Ammo Type: {weapon_details['equippingBlock']['ammoType']}")

        if ammo_type:
            # Filter weapons by ammo type
            slot_weapons = [weapon for weapon in slot_weapons if get_item_details(weapon['itemHash'])['equippingBlock']['ammoType'] == ammo_type]
            # st.write(f"Weapons with ammo type {ammo_type}: {len(slot_weapons)}")

        if slot_weapons:
            chosen_weapon = random.choice(slot_weapons)
            weapon_details = get_item_details(chosen_weapon['itemHash'])
            # st.write(f"Chosen weapon: {weapon_details['displayProperties']['name']}")
            return chosen_weapon
        else:
            st.write(f"No weapons found in slot {slot_hash} with ammo type {ammo_type}")
            return None

    def equip_weapon(access_token, character_id, item_id, membership_type):
        headers = {
            "X-API-Key": BUNGIE_API_KEY,
            "Authorization": f"Bearer {access_token}"
        }

        # Step 1: Transfer the item to the character's inventory
        transfer_payload = {
            "itemReferenceHash": 0,  # This will be ignored by the API
            "stackSize": 1,
            "transferToVault": False,
            "itemId": item_id,
            "characterId": character_id,
            "membershipType": membership_type
        }

        transfer_response = requests.post("https://www.bungie.net/Platform/Destiny2/Actions/Items/TransferItem/", headers=headers, json=transfer_payload)
        
        if transfer_response.status_code != 200:
            # st.error(f"Failed to transfer weapon. Status code: {transfer_response.status_code}")
            # Assuming transfer_response is a response object from the requests library
            response_json = transfer_response.json()
            # Extract the 'message' from the JSON response
            message = response_json.get('Message', 'No message found')
            # Display the entire JSON response
            st.json(response_json)
            if message == "There are no item slots available to transfer this item.":
                st.warning("No item slots available to transfer this item. Please make some space in your inventory.")
            return False

        # Step 2: Equip the item
        equip_payload = {
            "itemId": item_id,
            "characterId": character_id,
            "membershipType": membership_type
        }
        
        equip_response = requests.post("https://www.bungie.net/Platform/Destiny2/Actions/Items/EquipItem/", headers=headers, json=equip_payload)
        
        if equip_response.status_code != 200:
            st.error(f"Failed to equip weapon. Status code: {equip_response.status_code}")
            st.json(equip_response.json())
            return False

        return True

    # Display weapon details
    def display_weapon_details(item_details, item_instance_data=None):
        st.write(f"**{item_details['displayProperties']['name']}**")
        st.write(f"Type: {item_details['itemTypeDisplayName']}")
        
        if 'sockets' in item_details and item_instance_data and 'sockets' in item_instance_data:
            st.write("**Active Perks:**")
            for socket, instance_socket in zip(item_details['sockets']['socketEntries'], item_instance_data['sockets']['data']):
                if 'plugHash' in instance_socket:
                    plug_details = get_item_details(instance_socket['plugHash'])
                    if plug_details and plug_details['plug']['plugCategoryIdentifier'] in ['frames', 'intrinsics', 'barrels', 'magazines', 'perks']:
                        st.write(f"- {plug_details['displayProperties']['name']}")

    def display_equipped_weapons(character_id, character_data, equipment, vault_data, access_token, membership_type):
        st.subheader(f"Class: {get_class_name(character_data['classType'])}")
        weapon_slots = [
            (1498876634, "Kinetic"),
            (2465295065, "Energy"),
            (953998645, "Power")
        ]
        
        for slot_hash, slot_name in weapon_slots:
            weapon = next((item for item in equipment.get('items', []) if item.get('bucketHash') == slot_hash), None)
            if weapon:
                item_details = get_item_details(weapon['itemHash'])
                if item_details:
                    col1, col2, col3 = st.columns([1, 3, 1])
                    with col1:
                        st.image(f"https://www.bungie.net{item_details['displayProperties']['icon']}", width=50)
                    with col2:
                        display_weapon_details(item_details, weapon)
                    with col3:
                        if slot_name in ["Kinetic", "Energy"]:
                            ammo_type = st.radio(f"Ammo Type for {slot_name}", ["Primary", "Special"], key=f"ammo_{character_id}_{slot_hash}")
                            ammo_type_value = 1 if ammo_type == "Primary" else 2
                        else:
                            ammo_type = "Heavy"
                            ammo_type_value = 3
                        
                        if st.button(f"Randomize {slot_name}", key=f"randomize_{character_id}_{slot_hash}"):
                            new_weapon = get_random_weapon(vault_data, slot_hash, ammo_type_value)
                            if new_weapon:
                                new_item_details = get_item_details(new_weapon['itemHash'])
                                # st.write("Selected weapon:")
                                # display_weapon_details(new_item_details, new_weapon)
                                if equip_weapon(access_token, character_id, new_weapon['itemInstanceId'], membership_type):
                                    st.success(f"Equipped: {new_item_details['displayProperties']['name']}")

                            else:
                                st.write(f"No {slot_name} weapons found in vault for the selected ammo type")
            else:
                st.write(f"No {slot_name} weapon equipped")

    # Main app
    def main():
        access_token = get_access_token()
        if access_token:
            characters, character_equipment, vault_data, membership_type, membership_id = get_profile_and_equipment(access_token)
            if characters is not None and character_equipment is not None and vault_data is not None:
                character_classes = {get_class_name(data['classType']): char_id for char_id, data in characters.items()}
                selected_class = st.selectbox("Select a class", list(character_classes.keys()))
                selected_char_id = character_classes[selected_class]
                
                display_equipped_weapons(selected_char_id, characters[selected_char_id], character_equipment[selected_char_id], vault_data, access_token, membership_type)
            else:
                st.write("Failed to retrieve character data. Please try authenticating again.")
        else:
            st.write("Please authenticate with Bungie to view and manage your weapons.")

    if __name__ == "__main__":
        main()

elif modes == 'Subclass':
    destiny_subclasses = {
        "Warlock": {
            "Stormcaller": {
                "Super": ["Stormtrance", "Chaos Reach"],
                "Grenade": ["Arcbolt Grenade", "Flux Grenade", "Skip Grenade", "Flashbang Grenade", "Lightning Grenade", "Pulse Grenade", "Storm Grenade"],
                "Melee": ["Chain Lightning", "Ball Lightning"],
                "Class Ability": ["Healing Rift", "Empowering Rift"]
                
            },
            "Dawnblade": {
                "Super": ["Well of Radiance", "Daybreak"],
                "Grenade": ["Incendiary Grenade", "Swarm Grenade", "Tripmine Grenade", "Fusion Grenade", "Incendiary Grenade", "Thermite Grenade", "Firebolt Grenade", "Healing Grenade"],
                "Melee": ["Celestial Fire", "Incinerator Snap"],
                "Class Ability": ["Healing Rift", "Empowering Rift"]
            },
            "Voidwalker": {
                "Super": ["Vortex Novabomb", "Cataclysm Novabomb", "Nova Warp"],
                "Grenade":  ["Spike Grenade", "Vortex Grenade", "Voidwall Grenade", "Magnetic Grenade", "Suppressor Grenade", "Axion Bolt"],
                "Melee": ["Pocket Singularity"],
                "Class Ability": ["Healing Rift", "Empowering Rift"]
            },
            "Shadebinder":{
                "Super": ["Winter's Wrath"],
                "Grenade": ["Glacial Grenade", "Duskfield Grenade", "Coldsnap Grenade"],
                "Melee": ["Penumbral Blast"],
                "Class Ability": ["Healing Rift", "Empowering Rift"]
            },
            "Broodweaver":{
                "Super": ["Needlestorm"],
                "Grenade": ["Shackle Grenade", "Threadling Grenade", "Grapple Grenade"],
                "Melee": ["Arcane Needle"],
                "Class Ability": ["Healing Rift", "Empowering Rift"]
                
            }
        },
        "Titan": {
            "Striker": {
                "Super": ["Fists of Havoc", "Thundercrash"],
                "Grenade": ["Arcbolt Grenade", "Flux Grenade", "Skip Grenade", "Flashbang Grenade", "Lightning Grenade", "Pulse Grenade", "Storm Grenade"],
                "Melee": ["Seismic Strike", "Ballistic Slam", "Thunderclap"],
                "Class Ability": ["Towering Barricade", "Rally Barricade", "Thruster"]
            },
            "Sunbreaker": {
                "Super": ["Burning Maul", "Hammer of Sol"],
                "Grenade": ["Incendiary Grenade", "Swarm Grenade", "Tripmine Grenade", "Fusion Grenade", "Incendiary Grenade", "Thermite Grenade", "Firebolt Grenade", "Healing Grenade"],
                "Melee": ["Hammer Strike", "Throwing Hammer"],
                "Class Ability": ["Towering Barricade", "Rally Barricade"]
            },
            "Sentinel": {
                "Super": ["Sentinel Shield", "Ward of Dawn"],
                "Grenade":  ["Spike Grenade", "Vortex Grenade", "Voidwall Grenade", "Magnetic Grenade", "Suppressor Grenade", "Axion Bolt"],
                "Melee": ["Shield Bash", "Shield Throw"],
                "Class Ability": ["Towering Barricade", "Rally Barricade"]
            },
            "Behemoth":{
                "Super": ["Glacial Quake"],
                "Grenade": ["Glacial Grenade", "Duskfield Grenade", "Coldsnap Grenade"],
                "Melee": ["Shiver Strike"],
                "Class Ability": ["Towering Barricade", "Rally Barricade"]
            },
            "Berserker":{
                "Super": ["Bladefury"],
                "Grenade": ["Shackle Grenade", "Threadling Grenade", "Grapple Grenade"],
                "Melee": ["Frenzied Blades"],
                "Class Ability": ["Towering Barricade", "Rally Barricade"]
            }
        },
        "Hunter": {
            "Arcstrider": {
                "Super": ["Arc Staff", "Gathering Storm"],
                "Grenade": ["Arcbolt Grenade", "Flux Grenade", "Skip Grenade", "Flashbang Grenade", "Lightning Grenade", "Pulse Grenade", "Storm Grenade"],
                "Melee": ["Combination Blow", "Disorienting Blow"],
                "Class Ability": ["Marksman's Dodge", "Gambler's Dodge"],
            },
            "Gunslinger": {
                "Super": ["Deadshot", "Marksman", "Blade Barrage"],
                "Grenade": ["Incendiary Grenade", "Swarm Grenade", "Tripmine Grenade", "Fusion Grenade", "Incendiary Grenade", "Thermite Grenade", "Firebolt Grenade", "Healing Grenade"],
                "Melee": ["Knife Trick", "Lightweight Knife", "Weighted Throwing Knife", "Proximity Explosive Knife"],
                "Class Ability": ["Marksman's Dodge", "Gambler's Dodge", "Acrobat's Dodge"]
            },
            "Nightstalker": {
                "Super": ["Moebius Quiver", "Deadfall", "Spectral Blades"],
                "Grenade": ["Spike Grenade", "Vortex Grenade", "Voidwall Grenade", "Magnetic Grenade", "Suppressor Grenade", "Axion Bolt"],
                "Melee": ["Smoke Bomb"],
                "Class Ability": ["Marksman's Dodge", "Gambler's Dodge"]
            },
            "Revenant":{
                "Super": ["Silence and Squall"],
                "Grenade": ["Glacial Grenade", "Duskfield Grenade", "Coldsnap Grenade"],
                "Melee": ["Withering Blade"],
                "Class Ability": ["Marksman's Dodge", "Gambler's Dodge"]
            },
            "Threadrunner":{
                "Super": ["Silkstrike"],
                "Grenade": ["Shackle Grenade", "Threadling Grenade", "Grapple Grenade"],
                "Melee": ["Threaded Spike"],
                "Class Ability": ["Marksman's Dodge", "Gambler's Dodge"]
            }
        }
    }

    st.title("Random Subclass Generator")
    choice = st.selectbox("Which Class?", ('Warlock', 'Titan', 'Hunter'))

    col1, col2, col3 = st.columns(3)
    default = True
    with col1:
        grenade_box = st.checkbox('Grenade', value=default)
    with col2:
        melee_box = st.checkbox('Melee', value=default)
    with col3:
        class_ability_box = st.checkbox('Class Ability', value=default)

    if st.button('Randomize'):
        subclass_abilities = []
        class_selected = destiny_subclasses[str(choice)]
        subclass = random.choice(list(class_selected.keys()))
        super = random.choice(class_selected[subclass]['Super'])
        if grenade_box:
            grenade = random.choice(class_selected[subclass]['Grenade'])
            subclass_abilities.append(grenade)
        if melee_box:
            melee = random.choice(class_selected[subclass]['Melee'])
            subclass_abilities.append(melee)
        if class_ability_box:
            class_ability = random.choice(class_selected[subclass]['Class Ability'])
            subclass_abilities.append(class_ability)

        subclass_images = {
            'Stormcaller': 'images/warlock/Stormcaller.png',
            'Dawnblade': 'images/warlock/Dawnblade.png',
            'Voidwalker': 'images/warlock/Voidwalker.png',
            'Shadebinder': 'images/warlock/Shadebinder.png',
            'Broodweaver': 'images/warlock/Broodweaver.png',

            'Striker': 'images/titan/Striker.png',
            'Sunbreaker': 'images/titan/Sunbreaker.png',
            'Sentinel': 'images/titan/Sentinel.png',
            'Behemoth': 'images/titan/Behemoth.png',
            'Berserker': 'images/titan/Berserker.png',

            'Arcstrider': 'images/hunter/Arcstrider.png',
            'Gunslinger': 'images/hunter/Gunslinger.png',
            'Nightstalker': "images/hunter/Nightstalker.png",
            'Revenant': 'images/hunter/Revenant.png',
            'Threadrunner': 'images/hunter/Threadrunner.png'
        }

        st.subheader(f"{subclass} | {super} | {' | '.join(subclass_abilities)}")
        if subclass in subclass_images:
            image_path = subclass_images[subclass]
            image = Image.open(image_path)
            st.image(image)

