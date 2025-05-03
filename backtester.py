import numpy as np
import pandas as pd
import math
import json
#I imported matplotlib for the plot
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick


#Santiago Diaz Tolivia
#santidt@bu.edu

############# Blockhouse Interview Case ###############

############# function to extract data ################

def extract_first(data):
    '''This function sorts data by ts_event and venue and extracts first snapshot for all venues'''

    # sort data by the event
    data_sorted = data.sort_values(by=["ts_event", "publisher_id"])

    # take the first event for each venue at each time stamp
    snapshot_data = data_sorted.drop_duplicates(subset=["ts_event", "publisher_id"])
    snapshot_data = snapshot_data[[c for c in data.columns if any(k in c for k in ["00", "event", "publisher", "symbol"])]]
    # return a data frame with the extracted data
    return snapshot_data.groupby("ts_event", sort=True)

############## Baseline Algorithms ###################

def best_ask_baseline(snapshots, order_size):
    '''Calculates the baseline best ask'''
    #create variable to hold remaining order
    remaining = order_size
    #keep track of total cost
    total_cost = 0.0
    #keep track of shares filled
    total_filled = 0

    #iterate over all the ts_events
    for venues in snapshots:

        #if there are no veneus skip
        if not venues:
            continue

        #find the venue with the best ask price
        best_venue = min(venues, key=lambda v: v.ask)

        #fill shares as much as possible like a market order
        fill = min(best_venue.ask_size, remaining)

        #calculate cost per share if there is a fee
        cost_per_share = best_venue.ask + best_venue.fee
        #calculate total cost
        total_cost += fill * cost_per_share
        #update tracking variables
        remaining -= fill
        total_filled += fill

        #if there are 0 shares left break loop
        if remaining <= 0:
            break
    #calculate averge price per share
    avg_price = total_cost / total_filled if total_filled > 0 else 0.0

    #return benchmark
    return total_cost, avg_price


def twap_baseline(snapshots, ts_events, order_size):
    '''Calculates the baseline TWAP'''

    #find the start time and end time in order to make buckets
    ts_series = pd.to_datetime(ts_events, utc=True)
    start = ts_series.min()
    end = ts_series.max()

    #calculate total duration
    total_duration = (end - start).total_seconds()

    #calculate the buckets using ceiling so its evenly spread across time
    buckets = int(np.ceil(total_duration / 60))

    #compute the time delta for each bucket
    bucket_indices = (pd.Series(ts_series - start).dt.total_seconds() // 60).astype(int)
    bucket_indices = bucket_indices.clip(upper=buckets - 1)

    #calculate how much to trade per bucket
    order_chunk = order_size // buckets
    #start remainder variable for every bucket and tracking variables
    remainder = order_size % buckets
    remaining = order_size
    total_cost = 0.0
    total_filled = 0

    #iterate over the buckets
    for bucket in range(buckets):

        #update buckets
        bucket_remaining = order_chunk + (1 if bucket < remainder else 0)

        #get bucket indices
        indices = np.where(bucket_indices == bucket)[0]

        #iterate over the indices
        for i in indices:
            venues = snapshots[i]

            #for each venue in a snapshot
            for v in venues:

                #find the amount you can fill in the venues
                fill = min(v.ask_size, bucket_remaining)

                #calculate cost per share
                cost_per_share = v.ask + v.fee

                #total cost of the trade
                total_cost += fill * cost_per_share

                #update bucket numbers
                bucket_remaining -= fill
                remaining -= fill
                total_filled += fill

                #break loop
                if bucket_remaining <= 0 or remaining <= 0:
                    break
            #break loop
            if bucket_remaining <= 0 or remaining <= 0:
                break
        #break loop
        if remaining <= 0:
            break

    #give avergae price and total cost
    avg_price = total_cost / total_filled if total_filled > 0 else 0.0
    return total_cost, avg_price


def vwap_baseline(snapshots, order_size):
    '''Calculates the baseline VWAP'''

    #start counting variables
    remaining = order_size
    total_cost = 0.0
    total_filled = 0

    #iterate over the venues in each snapshot
    for venues in snapshots:

        #calculate total liquidity
        total_liquidity = sum(v.ask_size for v in venues)

        #test case break
        if total_liquidity == 0:
            continue

        #iterate over venues and make a liquidity weighted order
        for v in venues:

            #share amount is volume at venue over liquidity
            share = v.ask_size / total_liquidity

            #allocate the order size times the percent share in that venue
            alloc = int(order_size * share)
            #calculate the amount filled
            fill = min(alloc, v.ask_size, remaining)
            #calculate cost per share
            cost_per_share = v.ask + v.fee
            #total cost
            total_cost += fill * cost_per_share
            #update the fill and the remaining
            remaining -= fill
            total_filled += fill
            #break loop
            if remaining <= 0:
                break
        #break loop
        if remaining <= 0:
            break

    #return the total cost and average price
    avg_price = total_cost / total_filled if total_filled > 0 else 0.0
    return total_cost, avg_price


############## Class Venues to make the objects ################
class Venue:
    '''Create a class venue with attrubutes:
    ask = price per share
    ask_size = liquidity
    fee = fee
    rebate = rebate
    '''
    def __init__(self, ask, ask_size, fee= 0.0, rebate  = 0.0):
        #start all variables, here it could easly be adapted to include a fee or rebate
        self.ask = ask
        self.ask_size = ask_size
        self.fee = fee
        self.rebate = rebate

#helper function to extract the venues
def snapshot_venues(slice_):
    '''Creates a list of the venue objects for each snapshot'''

    # creates an empty list
    venues = []

    # slices the snapshot and iterates over the rows
    for _, row in slice_.sort_values("publisher_id").iterrows():
        # creates the venue object appending it to the list of venues
        venues.append(Venue(
            ask=row["ask_px_00"],
            ask_size=row["ask_sz_00"])
            #here we could add a fee or a rebate
        )

    # returns the list of venues
    return venues

############## Code Given for allocation and cost ##############

def compute_cost(split, venues, order_size, lambda_over, lambda_under, theta_queue):
    '''Compute cost function just like in the pseudocode and as explained in the paper'''

    #start tracking variables
    executed = 0
    cash_spent = 0

    #I changed the pseudocode (took out the len(venues) - 1 because I need to iterate through all venues
    for i in range(0,  len(venues)):
        #calculate the current executed
        exe = min(split[i], venues[i].ask_size)
        #keep track of total executed
        executed += exe
        #keep track of cash spent on shares
        cash_spent += exe * (venues[i].ask + venues[i].fee)
        #get rebate if any
        maker_rebate = max(split[i] - exe, 0) * venues[i].rebate
        #subtract rebate from cash spent
        cash_spent -= maker_rebate
    #calculate underfill
    underfill = max(order_size - executed, 0)
    #calculate overfill
    overfill = max(executed - order_size, 0)
    #penalization costs
    risk_pen = theta_queue * (underfill + overfill)
    cost_pen = lambda_under * underfill + lambda_over * overfill
    #return overall cost
    return cash_spent + risk_pen + cost_pen

def allocate(order_size, venues, lambda_over, lambda_under, theta_queue):
    #steps = 100 just like in the pseudocode
    step = 100
    splits = [[]]
    #changed the pseudocode because i want to iterate over all venues. In the case of the data
    #we only have one venue and if we subtract we dont iterate over anything
    for v in range(0, len(venues)):
        #start a new split
        new_split = []
        #iterate over every allocation for the current venue
        for alloc in splits:
            #calculate the number of shares used across venues
            used = sum(alloc)
            #get the min between the remaining shares and the size of the ask from current venue
            # because of this line there is no risk of overfilling
            max_v = min(order_size - used, venues[v].ask_size)
            #iterate from 0 to order size incrementing by step. We add step so we move by step
            for q in range(0, max_v + step, step):
                new_split.append(alloc + [q])
        #update splits
        splits = new_split

    #start the best cost at infinity so anything is better
    best_cost = math.inf
    best_split = []
    #iterate through allocations
    for alloc in splits:
        #dangerous line, if we remove this, then we can underfill. If not, our parameters dont affect our
        #model because order_size always equals executed
        if sum(alloc) != order_size:
            continue

        #send to compute cost function
        cost = compute_cost(alloc, venues, order_size, lambda_over, lambda_under, theta_queue)

        #keep track of lowest cost
        if cost < best_cost:
            best_cost = cost
            best_split = alloc
    #return the best split for the snapshot and the lowest cost
    return best_split, best_cost

################## Backtester and implementation ##################

def backtest_static_router(data,parent_order=5000,n_grid=7):
    '''Static Backtester, takes the data, the order size and the number of iterations'''

    #create the snapshot and the ts_event parallel lists
    snapshots, ts_events = [], []

    #for everu slice in extract_first we append the snapshot grouped by ts_event
    for ts, slice_ in extract_first(data):
        #here we get the data
        snapshots.append(snapshot_venues(slice_))
        #here we get the timestamp
        ts_events.append(ts)

    #set the hyperparameter grid
    lam_grid   = np.linspace(1,10, n_grid)
    theta_grid = np.linspace(1, 10, n_grid)

    #set the param tuple with the three variables and the iterator for all combinations
    param_space = [
        (lo, lu, tq)
        for lo in lam_grid
        for lu in lam_grid
        for tq in theta_grid
    ]


    #helper function to help do one pass over the data
    def run_once(param_triple, penalise=True, record_path=False):
        '''Runs once through the data:
        param_triple = the three parameters we are using
        penalise = true if penalty is applied for comparing to baseline,
                    false for comparing to benchmarks based on regular costs
        record_path = true if we want to plot
        '''
        #get variables from the parameter triple
        lambda_over, lambda_under, theta_queue = param_triple
        #start counting variables
        remaining, cash = parent_order, 0.0
        #keep track of cash for plotting
        path = []

        #set a max share that we trade at every snapshot
        #this is to reduce the risk of not selling because of the if sum(alloc) != order_size: continue
        CLIP = 500

        #iterate over snapshots
        for venues in snapshots:
            #break if lis is done
            if remaining == 0:
                #record for plotting
                if record_path:
                    path.append(cash)
                break

            #chose the order size for the snapshot between the clip and remaining shares
            slice_size = min(CLIP, remaining)

            #calculate the best split
            split, _ = allocate(slice_size, venues, lambda_over, lambda_under, theta_queue)

            #skip if split is empty
            if not any(split):
                #record cash spent
                if record_path:
                    path.append(cash)
                continue

            #start the variables if penalise is active for the
            lo = lambda_over  if penalise else 0.0
            lu = lambda_under if penalise else 0.0
            tq = theta_queue  if penalise else 0.0

            #calculate the cash spent
            cash_spent = compute_cost(split, venues, slice_size, lo, lu, tq)

            #keeps track of shares executed
            executed = sum(min(a, v.ask_size) for a, v in zip(split, venues))

            #updates variables
            cash      += cash_spent
            remaining -= executed

            #keeps track of plot
            if record_path:
                path.append(cash)

        #filled = totalshares filled
        filled  = parent_order - remaining
        #calculate average price
        avg_px  = cash / filled if filled else 0.0

        #return the cash spent and the average price
        return (cash, avg_px, path) if record_path else (cash, avg_px)

    #iterate over the parameters and find the lowest cost

    #start the variables
    best_cost   = math.inf
    best_params = None
    #iterate over all possible alloctions
    for triple in param_space:
        #calculate the cost through run once
        cost, _ = run_once(triple, penalise=True)

        #if cost is best
        if cost < best_cost:
            #save params
            best_cost, best_params = cost, triple
    #run once without the penalization to compare to baselines
    tuned_cost, tuned_avg, cum_path = run_once(best_params, penalise=False, record_path=True)

    #plot
    plt.figure(figsize=(10, 6))
    plt.plot(cum_path, label="Strategy (penalised)")
    plt.xlabel("Snapshot index")
    plt.ylabel("Cumulative cost ($)")
    plt.title("Cumulative Execution Cost")
    plt.grid(True)

    # get the Axes and turn off scientific notation
    ax = plt.gca()
    ax.ticklabel_format(style='plain', axis='y')

    # format y‐ticks as dollars
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter('${x:,.0f}'))

    plt.tight_layout()
    plt.savefig("results.png", dpi=150)
    plt.close()
    print("Cumulative-cost plot written to results.png")


    #baselines using their individual functions one pass each
    best_ask_cost, best_ask_avg = best_ask_baseline(snapshots, parent_order)
    twap_cost,     twap_avg     = twap_baseline(snapshots, ts_events, parent_order)
    vwap_cost,     vwap_avg     = vwap_baseline(snapshots, parent_order)

    #calculate the bps savings
    def bps_saving(baseline_cost):
        return 10_000 * (baseline_cost - tuned_cost) / baseline_cost

    #create a dictionary of results
    result = {
        "best_parameters": {
            "lambda_over" : best_params[0],
            "lambda_under": best_params[1],
            "theta_queue" : best_params[2],
        },

        "total_cost_smart_order_router"   : tuned_cost,
        "average_price": tuned_avg,

        "best_ask": {
            "total_cost"  : best_ask_cost,
            "average_price": best_ask_avg,
            "bps_savings" : bps_saving(best_ask_cost)
        },

        "twap": {
            "total_cost"  : twap_cost,
            "average_price": twap_avg,
            "bps_savings" : bps_saving(twap_cost)
        },

        "vwap": {
            "total_cost"  : vwap_cost,
            "average_price": vwap_avg,
            "bps_savings" : bps_saving(vwap_cost)
        }
    }
    print(json.dumps(result, indent=2))

if __name__ == "__main__":

    #keep track of running time
    import sys, time

    #read the data, one is the original other is synthetic data
    df = pd.read_csv("l1_day.csv")
    df_different_venues = pd.read_csv("l1_day_random_venues.csv")

    #run backtest and keep json output
    t0 = time.perf_counter()
    backtest_static_router(df)
    dt = time.perf_counter() - t0

    #print time it took to run
    print(f"# finished in {dt:0.2f} s", file=sys.stderr)

