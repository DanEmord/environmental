import urequests

def get_location(url):
    try:
        response = urequests.get(url)
        if response.status_code == 200:
            return response.content.decode("utf-8").strip()
        else:
            return "unknown"
    except Exception as e:
        return "unknown"