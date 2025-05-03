# BlockhouseCase
Smart Order Router across multiple venues

**Dear Blockhouse Hiring Team,**
Thank you so much for the opportunity to do the case. It was extremely interesting to learn about Rama Cont's and Arseniy Kukanov's paper "Optimal Order Placement in Limit Order Markets. I hope you like the conclusions I drew and how we can improve the code to further extend on their research in stochstic convex optimization. 

To start the case, I read the case and looked at the data. In the case, we were asked to implement a backtester that can tune the hyperparameters Lambda_under, Lambda_over, and Theta_queue. These parameters as Cont and Kukanov explain are "Implicit execution costs." I implemented the code in pseudocode.txt and then tried to build a backtester that could find the best hyper parameters. 

**Building Helper Functions**
The first part of the problem was to build a function that could extract the first ts_event for every venue at each timestamp. Therefore I built the extract first which extracts the ts_events for each venue and drops duplicates. Then it returns the snapshots grouped by time stamp. Then I built a class Venue to create objects inside each timestamp with the venues ask price, ask size, fee, and rebate. Althought we didnt have fees or rebates in the data, I wanted to make sure that the code is easly adaptable in the case of fees and rebates. I also created a function to iterate over rows at each snapshot and create the venues. Once these functions were ready, we could move to the baselines, allocate and compute_cost functions.

**Building Baselines**
To build the baselines it was pretty straightforward. We do a best ask which just takes the venue with the best ask at every snapshot and fills with market orders. Then the TWAP which is time weighted average price. Here we made buckets with 60 seconds each and implemented the trades over the whole tape. Finally VWAP which is volume weighted average price which we implemented at every snapshot weighting the order based on the volume of all venues. Since there was only one venue in our data it ended up performing exactly as the best ask but this will change if we use data with more venues (it did when tested). 

**Implementing Pseudocode**
The pseudocode had a very precise way of implementing the allocation of shares across exchanges. The first thing to point out is that it did not allow for overfill because of the line: exe ← min(split[i], venues[i].ask_size). It takes the min between the split on that venue and the ask_size therefore not allowing executed to be higher than the ask_size. This could be done on purpose since the data had only one venue and in the paper we learn that the optimal allocation in the one venue setting there is never overfill. Another thing that cought my attention was the line: If sum(alloc) != order_size: Continue. This line is very rigid in the sense that if there is never an optimal allocation that adds up to the order size we skip the allocation all together. It also does not allow for underfills and makes our parameters not affect the results. Some improvements to be able to use our hyperparameters would be to relax that constraint or remove it all together. Keeping that constraint,the data still outperforms the baselines by 3 basis points because at some point in the data set there is an ask_size greater than 5000 and cheaper than previous or average prices. But if we were trying to buy more shares or it is implemented on a different data set it could potentially go through the data without trading, or underperform to the baselines. 

**Building the Backtester**
When building the backtester, I implemented a grid search using np.linespace. I also built a helper function called run_once which does one run through the data with a set of parameters. This function is inside the bakctest_static_router function which actually iterates over the parameters and calls run_once. The run_once function also keeps track of the cash spent in order to plot it for the cummulative cost chart. In my backtester, I decided to implement a clip on the order size because I did not want to take the risk of not trading when the model is tested. If we have a model that has an order size of 5000 at the start, if in the time period when it trades there is no ask size greater than 5000, the sum of the allocations will never be equal to 5000 therefore pushing the model to not trade. In order to reduce this risk, we implemented a reduction on the order size per snapshot still keeping track of the remaining 5000 shares. In order to make the code work under any condition we would need to relax the constraint sum(alloc) != order_size: Continue and actually penalize the model with the implicit execution costs. 

**Simulating Data with Different Venues**
In order to test my code with a data set that utilized different venues, I created a copy of the original data set and randomized the publisher_id column to give it a number between 1, 2, and 3. This way I was able to make sure the allocate function works as intended when there are multiple venues in the data set. It worked and still beat the baselines. 


**Conclusions:**
It is possible to find a set of parameters that help improve the allocation. In order to do that we need to get rid of the constraint that the order size must be equal to the sum of the allocations. If we do this, then we can balance between the allocations by penalizing a 0 trade with a bigger underfill. Since in the compute cost function we also calculate the cost of the trade given ask price and fee, the parameters need be large enough to balance the underfill difference. In order to tune the parameters correctly we would need to allow for underfill and overfill so that the smart router decides between trading agressively, trading less, or not trading. I actually implemented this and found some parameters that were penalizing the smart order router. That being said, I wanted to stay true to the pseudocode for the final submission and just explain the conclusions I drew from playing with the model these last 3 days.

**Why λ and θ do not affect our results
The allocator exactly follows allocator_pseudocode.txt, which (1) caps per‑venue orders at displayed size and (2) keeps only splits that sum to the requested order_size. Under those two rules the executed quantity always equals the order_size, so the under‑/over‑fill terms in the Cont–Kukanov cost function are zero by construction. We therefore retain the λ/θ grid for completeness but note that all parameter tuples yield identical allocations and costs.**

**How can we improve on this optimization:**
Apart from what was already discussed, other ways to improve the static optimization setting would be to take into account the queue position and slippage. Currently the allocator assumes immidiate fills at quoted sizes ignoring partial fills or slippage. We could model this with a probabilistic fill model using a poisson arrival process or exponential decay to make the settings more realistic. Ways to improve on this optimization would be to implement the stochastic optimization model introduced in the paper where we find the distribution of the order flow and approximate the ideal step size and parameters. 

Once again, thank you so much for the opportuniy to showcase my skills. I enjoyed building the model, debugging it, and playing around with different allocate implementations in order to understand the problem in depth and also come to the conclusions I discovered. I hope you all are having a great weekend!

Looking forward to hearing from you!

Sincerly, 
Santiago Diaz Tolivia



