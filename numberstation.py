import json
import time
import threading
from datetime import datetime
from random import random
from bottle import post, request, route, run, static_file, view, get
from queue import Queue
from bottle.ext.websocket import GeventWebSocketServer
from bottle.ext.websocket import websocket

from animation import Numbers, Chase, hsv_to_rgb, GrowingNumbers
from dmx import DMX, RGB


class Number:
    def __init__(self, description, initial, color, increment, t0):
        self.description = description
        self.initial = initial
        self.color = color
        self.increment = increment
        self.t0 = t0
        self.animation = GrowingNumbers(initial, color, increment, t0)

    @property
    def now(self):
        if type(self.initial) == int or type(self.initial) == float:
            return self.initial + int((datetime.now() - self.t0).total_seconds() * self.increment)
        return self.initial

class PlaceholderNumber(Number):
    def __init__(self):
        self.description = 'A random fact'
        self.initial = '???'
        self.color = (128, 128, 128)
        self.increment = 0
        self.t0 = datetime.now()
        self.animation = GrowingNumbers(0, self.color, self.increment, self.t0)

    def now(self):
        return "???"


def get_coming_up():
    coming_up = list(priorityQueue.queue)
    coming_up.extend(list(backgroundQueue.queue))
    if len(coming_up) == 0:
        coming_up = [PlaceholderNumber()]
    return coming_up

current_number = None
interval = 10
clients = []


@route('/')
@view('index')
def index():
    return {
        'current': current_number,
        'coming_up': get_coming_up(),
    }


@route('/kiosk')
@view('kiosk')
def index():
    return {
        'current': current_number,
        'coming_up': get_coming_up(),
    }


@route('/number')
@view('number')
def number():
    d = request.query.description or request.query.d or 'unknown number'
    n = request.query.number or request.query.n or ''
    r = request.query.r or 0
    g = request.query.g or 0
    b = request.query.b or 0
    i = request.query.i or 0
    try:
        n = int(n)
    except ValueError:
        pass
    token = request.query.token or 0
    if r == 0 and g == 0 and b == 0:
        (r, g, b) = hsv_to_rgb(random(), 1, 1)
    number = Number(d, n, (r, g, b), int(i), datetime.now())
    if token == 'geheim':
        priorityQueue.put(number)
        when = len(priorityQueue.queue) * interval
    else:
        backgroundQueue.put(number)
        when = (len(priorityQueue.queue) + len(backgroundQueue.queue)) * interval
    return {
        'number': number,
        'when': when
    }


@get('/ws', apply=[websocket])
def ws(ws):
    global clients
    global current_number
    if ws is None:
        return
    clients.append(ws)
    ws.send(number_to_json(current_number))
    while True:
        if ws.receive() is None:
            break
    clients.remove(ws)

@route('/static/<filename>')
def server_static(filename):
    return static_file(filename, root='static')


def number_to_json(number):
    coming_up = get_coming_up()
    return json.dumps({
        'number': {
            'description': current_number.description,
            'initial': current_number.initial,
            'now': current_number.now,
            'color': {
                'r': current_number.color[0],
                'g': current_number.color[1],
                'b': current_number.color[2],
            },
            'increment': current_number.increment,
            't0': current_number.t0.isoformat(),
        },
        'coming_up': [{
            'initial': n.initial,
            'description': n.description,
            'color': {'r': n.color[0], 'g': n.color[1], 'b': n.color[2]},
        } for n in coming_up]
    })

def send_ws():
    global clients
    for ws in clients:
        def send():
            try:
                ws.send(number_to_json(current_number))
            except Exception:
                self.wsstats_clients.remove(ws)

        t = threading.Thread(target=send, daemon=True).start()


def set_animation(n: Numbers) -> None:
    dmx.animation = n


def queue_worker() -> None:
    global current_number
    while True:
        if not priorityQueue.empty():
            current_number = priorityQueue.get()
        elif not backgroundQueue.empty():
            current_number = backgroundQueue.get()
        else:
            # dmx.animation = Chase((255,0,0))
            # set_animation(Numbers(f'{random()*100000000000:011.0f}', (hsv_to_rgb(random(), 1, 1))))
            current_number = numbers[int(random() * len(numbers))]
        set_animation(current_number.animation)
        send_ws()
        time.sleep(interval)


numbers = [
    Number('World Population', 8_195_809_906, (255, 255, 0), 2.2,
           datetime(2024, 12, 24, 12, 0, 0)),
    Number('Computers produced in 2024', 225_315_180, (255, 0, 255), 5.1,
           datetime(2024, 12, 24, 12, 0, 0)),
    Number('Newspapers circulated', 0, (0, 0, 255), 200_873_303.0 / 365 / 24 / 60 / 60,
           datetime(2024, 1, 1, 0, 0, 0)),
    Number('CO2 emissions this year', 0, (255, 255, 0), 38_675_262_757.0 / 365 / 24 / 60 / 60,
           datetime(2024, 1, 1, 0, 0, 0)),
    Number('Google searches', 8_500_000_000, (255, 0, 255), 8_500_000_000.0 / 24 / 60 / 60,
           datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)),
    Number('Water used next year', 0, (0, 0, 255), 4_000_000_000.0 / 365 / 24 / 60 / 60,
           datetime(2024, 1, 1, 0, 0, 0)),
    Number('Seconds until 39C3 is over', 0, (255, 255, 0), 1,
           datetime(2025, 12, 30, 18, 0, 0)),
    Number('Seconds after Robots annihilated humans', 0, (255, 0, 255), 1,
           datetime(2024, 12, 27, 11, 0, 0)),
    Number('All your base are belong to us', 0, (255, 0, 255), 1,
           datetime(2025, 12, 27, 11, 0, 0)),
]

backgroundQueue = Queue(maxsize=500)
priorityQueue = Queue(maxsize=250)

dmx = DMX('127.0.0.1', maxchan=264, universe=1, refresh_rate=5)

for digit in range(11):
    for segment in range(8):
        dmx._rgbs.append(RGB(dmx, 8 * 3 * digit + 3 * segment + 1, 0))

threading.Thread(target=queue_worker, daemon=True).start()

dmx.start()

run(host='127.0.0.1', port=8080, reloader=False, debug=True, server=GeventWebSocketServer)
