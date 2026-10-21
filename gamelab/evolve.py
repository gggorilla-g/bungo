"""遺伝的アルゴリズム：行動の列を親から受け継ぎ、死んだ地点の少し前から先を書き換える"""
import random, json, sys, time
import game

POP, ELITE = 120, 12
GLEN = game.MAXT // game.STEP

def fitness(a):
    f = a.maxx
    if a.won: f += 100000 - a.t * 10
    return f

def mutate(g, death_t, rate=0.06):
    g = g[:]
    k0 = max(0, death_t // game.STEP - random.randint(3, 25))
    for i in range(k0, GLEN):
        if random.random() < rate * (3 if i < k0 + 30 else 1): g[i] = random.randrange(6)
    return g

def main(gens=300, seed=1, out="history.json"):
    random.seed(seed)
    pop = [[random.choice([2, 2, 2, 5, 1, 4]) for _ in range(GLEN)] for _ in range(POP)]
    hist, deaths, t0 = [], 0, time.time()
    first_win = None
    for gen in range(1, gens + 1):
        res = []
        for g in pop:
            a, _ = game.run(g)
            res.append((fitness(a), g, a))
        res.sort(key=lambda r: -r[0])
        d = sum(1 for r in res if not r[2].won)
        deaths += d
        wins = POP - d
        best = res[0][2]
        causes = {}
        for r in res:
            if r[2].cause: causes[r[2].cause] = causes.get(r[2].cause, 0) + 1
        hist.append({"gen": gen, "best_x": best.maxx, "won": wins, "deaths_total": deaths,
                     "causes": causes, "genomes": [r[1] for r in res[:40]]})
        if wins and first_win is None: first_win = gen
        print(gen, int(best.maxx), wins, deaths, causes, f"{time.time()-t0:.0f}s", flush=True)
        if first_win and gen >= first_win + 15: break
        elites = [r[1] for r in res[:ELITE]]
        nxt = elites[:]
        while len(nxt) < POP:
            p = random.choice(elites[:10]) if random.random() < .7 else random.choice(elites)
            pa = res[[r[1] for r in res].index(p)][2]
            nxt.append(mutate(p, pa.t))
        pop = nxt
    json.dump(hist, open(out, "w"))

KEEP = {1, 2, 3, 5, 8, 12, 20, 30, 50, 75, 100, 150, 200}
if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 300)
