# References, in IEEE form

The plan's citations, [1] to [106], found and verified by web search on 2 November 2026 (one entry marked where a detail could not be verified), grouped by theme. Under each theme, *What it means for us* says what the sources establish and how the line uses or should use it. Thirty-six are IEEE publications; the rest are the field's founding books and journals.

## Contents

- Evolution strategies: [1] to [8]
- SPSA and stochastic approximation: [9] to [16]
- Genetic algorithms and neuroevolution: [17] to [24]
- Noisy fitness and statistical gates: [25] to [32]
- Island models and parallel evolutionary algorithms: [33] to [40]
- Quality diversity and niches: [41] to [49]
- Procedural personas and player modelling: [50] to [57]
- Self-play, coevolution and population-based training: [58] to [65]
- Imitation and behaviour cloning: [66] to [73]
- Formation control and leader-follower: [74] to [81]
- RTS game AI, balance and economy: [82] to [89]
- Curriculum and evaluation protocol: [90] to [97]
- Network width, depth and small controllers: [98] to [104]
- Ballistics and small UAV performance: [105] to [105]
- Human-automation interaction and adjustable autonomy: [106] to [106]

## Evolution strategies

[1] I. Rechenberg, *Evolutionsstrategie: Optimierung technischer Systeme nach Prinzipien der biologischen Evolution*. Frommann-Holzboog, Stuttgart-Bad Cannstatt (problemata series), 1973. https://www.Gwern.net/doc/reinforcement-learning/exploration/1973-rechenberg.pdf

[2] H.-P. Schwefel, *Numerical Optimization of Computer Models*. John Wiley & Sons, Chichester (English translation by M. Finnis of the 1977 Birkhauser text), 1981.

[3] H.-G. Beyer and H.-P. Schwefel, “Evolution strategies: A comprehensive introduction,” *Natural Computing*, vol. 1, no. 1, pp. 3-52, 2002, doi: 10.1023/A:1015059928466. https://gwern.net/doc/reinforcement-learning/model-free/2002-beyer.pdf

[4] N. Hansen and A. Ostermeier, “Completely Derandomized Self-Adaptation in Evolution Strategies,” *Evolutionary Computation*, vol. 9, no. 2, pp. 159-195, 2001, doi: 10.1162/106365601750190398. http://www.cmap.polytechnique.fr/~nikolaus.hansen/cmaartic.pdf

[5] D. Wierstra, T. Schaul, T. Glasmachers, Y. Sun, J. Peters and J. Schmidhuber, “Natural Evolution Strategies,” *Journal of Machine Learning Research*, vol. 15, no. 27, pp. 949-980, 2014. https://www.jmlr.org/papers/v15/wierstra14a.html

[6] T. Salimans, J. Ho, X. Chen, S. Sidor and I. Sutskever, “Evolution Strategies as a Scalable Alternative to Reinforcement Learning,” *arXiv preprint arXiv:1703.03864 (OpenAI)*, 2017, doi: 10.48550/arXiv.1703.03864. https://arxiv.org/abs/1703.03864

[7] P. Chrabaszcz, I. Loshchilov and F. Hutter, “Back to Basics: Benchmarking Canonical Evolution Strategies for Playing Atari,” *Proceedings of the 27th International Joint Conference on Artificial Intelligence (IJCAI-18)*, pp. 1419-1426, 2018, doi: 10.24963/ijcai.2018/197. https://www.ijcai.org/proceedings/2018/0197.pdf

[8] C. Igel, “Neuroevolution for reinforcement learning using evolution strategies,” *Proceedings of the 2003 IEEE Congress on Evolutionary Computation (CEC 2003)*, vol. 4, pp. 2588-2595, 2003, doi: 10.1109/CEC.2003.1299414.

**What it means for us.** Evolution strategies began as a parent, a Gaussian step and a keep-or-discard rule, with the step size adapted by the 1/5 success rule [1]; the multimembered (mu+lambda) and (mu,lambda) forms added a population, recombination and self-adapted step sizes [2], and the standard survey gives the notation and the argument that a noisy fitness favours comma selection with a population over a lone climber [3]. CMA-ES adapts a full covariance and controls the step by an evolution path, which pays most when the coordinates are mis-scaled and correlated [4]; natural evolution strategies recast this as a natural-gradient step on a search distribution, with rank-based fitness shaping and the separable SNES form for larger weight vectors [5]. On policy networks, a plain NES with mirrored perturbations trains on a thousand workers by shipping only seeds and scalar returns [6], a canonical (mu,lambda)-ES matches it on Atari while varying widely between runs [7], and CMA-ES over a small policy network's weights was shown competitive for reinforcement learning in 2003 [8]. Our line is a (1+1)-style climber over about 135 brain weights with a step set by hand. The literature says to adapt that step from the success rate or an evolution path, to rank the census scores before any update so blowouts cannot drag it, to try the plain generational ES before anything cleverer, and to keep the gate and the held-out reads because run-to-run variance is the rule. For the transform's few hundred numbers a separable NES is the affordable form; a full covariance is for the 135 brain weights only.

## SPSA and stochastic approximation

[9] J. C. Spall, “Multivariate stochastic approximation using a simultaneous perturbation gradient approximation,” *IEEE Transactions on Automatic Control*, vol. 37, no. 3, pp. 332-341, 1992, doi: 10.1109/9.119632. https://ui.adsabs.harvard.edu/abs/1992ITAC...37..332S/abstract

[10] J. C. Spall, “Implementation of the simultaneous perturbation algorithm for stochastic optimization,” *IEEE Transactions on Aerospace and Electronic Systems*, vol. 34, no. 3, pp. 817-823, 1998, doi: 10.1109/7.705889. https://ieeexplore.ieee.org/document/705889

[11] H. Robbins and S. Monro, “A Stochastic Approximation Method,” *The Annals of Mathematical Statistics*, vol. 22, no. 3, pp. 400-407, 1951, doi: 10.1214/aoms/1177729586. https://projecteuclid.org/euclid.aoms/1177729586

[12] J. Kiefer and J. Wolfowitz, “Stochastic Estimation of the Maximum of a Regression Function,” *The Annals of Mathematical Statistics*, vol. 23, no. 3, pp. 462-466, 1952, doi: 10.1214/aoms/1177729392. https://projecteuclid.org/euclid.aoms/1177729392

[13] P. Sadegh and J. C. Spall, “Optimal random perturbations for stochastic approximation using a simultaneous perturbation gradient approximation,” *IEEE Transactions on Automatic Control*, vol. 43, no. 10, pp. 1480-1484, 1998, doi: 10.1109/9.720513. https://orbit.dtu.dk/en/publications/optimal-random-perturbations-for-stochastic-approximation-using-a/

[14] L. Gerencsér, “Convergence Rate of Moments in Stochastic Approximation with Simultaneous Perturbation Gradient Approximation and Resetting,” *IEEE Transactions on Automatic Control*, vol. 44, no. 5, pp. 894-905, 1999, doi: 10.1109/9.763206. https://www.jhuapl.edu/SPSA/PDF-SPSA/Gerencser_TAC99.pdf

[15] J. C. Spall, *Introduction to Stochastic Search and Optimization: Estimation, Simulation, and Control*. Wiley-Interscience, Hoboken, NJ, 2003, doi: 10.1002/0471722138. https://www.cs.utexas.edu/~shivaram/readings/b2hd-Spall2003.html

[16] H. J. Kushner and G. G. Yin, *Stochastic Approximation and Recursive Algorithms and Applications*. Springer, Stochastic Modelling and Applied Probability vol. 35, 2nd ed., 2003, doi: 10.1007/b97441. https://www.springer.com/978-0-387-00894-3

**What it means for us.** Stochastic approximation finds a root from noisy observations with gains that sum to infinity while their squares sum to a finite number [11], and Kiefer and Wolfowitz turned it toward a maximum using finite differences of noisy function values [12]. SPSA perturbs every parameter at once and needs two loss reads a step regardless of dimension [9]; the implementation guide gives the gain exponents, the stability constant, Bernoulli perturbations, iterate blocking and gradient averaging under heavy noise [10], and the +/-1 perturbation is proved optimal among perturbation distributions [13]. With a resetting rule that keeps the iterate in a bounded domain, the error moments shrink at a known rate [14]; the textbooks give the ODE method, convergence under constrained and asynchronous updates, and the statistical comparison of algorithms [15], [16]. Our SPSA pass treats one census as one noisy loss read. The gains must decay as the theory requires or a fixed step on census noise never settles; the perturbations should stay Bernoulli; the locked ranges and the reset to main are the bounded domain the moment bounds assume; and reads returning out of order from many machines are the asynchronous case Kushner and Yin cover.

## Genetic algorithms and neuroevolution

[17] J. H. Holland, *Adaptation in Natural and Artificial Systems: An Introductory Analysis with Applications to Biology, Control, and Artificial Intelligence*. University of Michigan Press, Ann Arbor (1st MIT Press ed., Cambridge, MA, 1992), 1975. https://library.holycross.edu/Record/b1307074

[18] D. E. Goldberg, *Genetic Algorithms in Search, Optimization, and Machine Learning*. Addison-Wesley, Reading, MA, 1989. https://lib.ecu.edu/catalog-preview/catalog/359988

[19] X. Yao, “Evolving Artificial Neural Networks,” *Proceedings of the IEEE*, vol. 87, no. 9, pp. 1423-1447, 1999, doi: 10.1109/5.784219. https://scholars.ln.edu.hk/en/publications/evolving-artificial-neural-networks/

[20] K. O. Stanley and R. Miikkulainen, “Evolving Neural Networks through Augmenting Topologies,” *Evolutionary Computation*, vol. 10, no. 2, pp. 99-127, 2002, doi: 10.1162/106365602320169811. https://dl.acm.org/doi/10.1162/106365602320169811

[21] D. Floreano, P. Dürr and C. Mattiussi, “Neuroevolution: from architectures to learning,” *Evolutionary Intelligence*, vol. 1, no. 1, pp. 47-62, 2008, doi: 10.1007/s12065-007-0002-4. https://infoscience.epfl.ch/record/112676

[22] S. Risi and J. Togelius, “Neuroevolution in Games: State of the Art and Open Challenges,” *IEEE Transactions on Computational Intelligence and AI in Games*, vol. 9, no. 1, pp. 25-41, 2017, doi: 10.1109/TCIAIG.2015.2494596. https://researcher.itu.dk/en/publications/neuroevolution-in-games-state-of-the-art-and-open-challenges/

[23] F. P. Such, V. Madhavan, E. Conti, J. Lehman, K. O. Stanley and J. Clune, “Deep Neuroevolution: Genetic Algorithms Are a Competitive Alternative for Training Deep Neural Networks for Reinforcement Learning,” *arXiv preprint arXiv:1712.06567 (Uber AI Labs)*, 2017, doi: 10.48550/arXiv.1712.06567. https://arxiv.org/abs/1712.06567

[24] K. O. Stanley, J. Clune, J. Lehman and R. Miikkulainen, “Designing neural networks through neuroevolution,” *Nature Machine Intelligence*, vol. 1, no. 1, pp. 24-35, 2019, doi: 10.1038/s42256-018-0006-z. https://gpbib.cs.ucl.ac.uk/gp-html/Stanley_2019_NMI.html

**What it means for us.** Genetic algorithms set out populations, selection, crossover and mutation, with the schema theorem as the first account of why a population finds good regions [17], and the textbook added fitness scaling and niching for keeping diversity [18]. Evolving network weights by population search meets the permutation problem: two nets with different hidden-unit orderings give a broken child under crossover [19], which NEAT answers with innovation numbers, speciation and growth from a minimal net [20]; the surveys set direct against indirect encodings and evolving a learning rule against evolving weights [21], and the games survey names noisy fitness and believable, varied agents as open problems [22]. A plain GA with a seed-chain encoding trains networks of millions of weights on Atari [23], and the modern review puts diversity ahead of pure objectives on deceptive tasks [24]. The GPU arena with islands and a hall of fame is a genetic algorithm in Holland's sense. The sources say to recombine the transform's weights by mutation only, or align hidden units first; to store a lineage as a list of seeds rather than weights; and to treat the transform's width and depth as something the search can set rather than a number fixed in advance.

## Noisy fitness and statistical gates

[25] Y. Jin and J. Branke, “Evolutionary Optimization in Uncertain Environments—A Survey,” *IEEE Transactions on Evolutionary Computation*, vol. 9, no. 3, pp. 303-317, 2005, doi: 10.1109/TEVC.2005.846356. https://www.cs.le.ac.uk/people/sy11/ECiDUE/JinBranke-TEVC05.pdf

[26] D. V. Arnold and H.-G. Beyer, “Local performance of the (1+1)-ES in a noisy environment,” *IEEE Transactions on Evolutionary Computation*, vol. 6, no. 1, pp. 30-41, 2002, doi: 10.1109/4235.985690. https://doi.org/10.1109/4235.985690

[27] O. Maron and A. W. Moore, “Hoeffding Races: Accelerating Model Selection Search for Classification and Function Approximation,” *Advances in Neural Information Processing Systems 6 (NIPS 1993)*, vol. 6, pp. 59-66, 1993. https://papers.neurips.cc/paper_files/paper/1993/file/02a32ad2669e6fe298e607fe7cc0e1a0-Paper.pdf

[28] M. Birattari, T. Stützle, L. Paquete and K. Varrentrapp, “A Racing Algorithm for Configuring Metaheuristics,” *Proceedings of the Genetic and Evolutionary Computation Conference (GECCO 2002), Morgan Kaufmann*, pp. 11-18, 2002. https://cs.ubc.ca/labs/algorithms/Courses/CPSC536H-10/Materials/BirEtAl02.pdf

[29] A. Wald, “Sequential Tests of Statistical Hypotheses,” *The Annals of Mathematical Statistics*, vol. 16, no. 2, pp. 117-186, 1945, doi: 10.1214/aoms/1177731118. https://doi.org/10.1214/aoms/1177731118

[30] N. Hansen, A. S. P. Niederberger, L. Guzzella and P. Koumoutsakos, “A Method for Handling Uncertainty in Evolutionary Optimization With an Application to Feedback Control of Combustion,” *IEEE Transactions on Evolutionary Computation*, vol. 13, no. 1, pp. 180-197, 2009, doi: 10.1109/TEVC.2008.924423. https://researchportal.ip-paris.fr/en/publications/a-method-for-handling-uncertainty-in-evolutionary-optimization-wi/

[31] V. Heidrich-Meisner and C. Igel, “Hoeffding and Bernstein Races for Selecting Policies in Evolutionary Direct Policy Search,” *Proceedings of the 26th International Conference on Machine Learning (ICML 2009), ACM*, pp. 401-408, 2009, doi: 10.1145/1553374.1553426. https://icml.cc/Conferences/2009/papers/229.pdf

[32] S.-H. Kim and B. L. Nelson, “A fully sequential procedure for indifference-zone selection in simulation,” *ACM Transactions on Modeling and Computer Simulation*, vol. 11, no. 3, pp. 251-273, 2001, doi: 10.1145/502109.502111. https://www.cs.utexas.edu/~shivaram/readings/b2hd-KimNelson2001.html

**What it means for us.** The survey of evolutionary optimisation under noise sorts the answers into explicit averaging by resampling, implicit averaging by larger populations, and modified selection [25]; our censuses are the first, the arena the second and the z-score gate the third. On the noisy sphere, not re-reading the parent overvalues it, and there is an optimal resampling rate for a given noise and step [26]. Racing evaluates candidates on a growing sample and drops any whose confidence interval has left the leader's [27]; F-Race does the same with a paired rank test over blocked instances [28]; and Hoeffding and Bernstein races attached to CMA-ES policy search found that ranking policies is far less noise-sensitive than estimating their returns [31]. Wald's sequential test stops as soon as the likelihood ratio crosses a threshold fixed by the error rates, on average with far fewer observations than a fixed-size test [29]; procedure KN gives the number of evaluations a selection needs for the smallest difference worth detecting [32]; and a rank-change count over a few re-evaluated individuals tells when the evaluation count or the step must grow [30]. For us: a census of 400 to 800 matches need not run in full for every candidate, since seeds block candidate and main and a paired rank test or a sequential test can retire a clear loser early; the held-out reads are the re-read of the incumbent the (1+1) analysis asks for; and the floors (built 1, road 0.5, kills less deaths 0.10) are an indifference zone, so KN gives the census size they imply.

## Island models and parallel evolutionary algorithms

[33] E. Alba and M. Tomassini, “Parallelism and evolutionary algorithms,” *IEEE Transactions on Evolutionary Computation*, vol. 6, no. 5, pp. 443-462, 2002, doi: 10.1109/TEVC.2002.800880. https://ieeexplore.ieee.org/abstract/document/1041554

[34] D. Whitley, S. Rana and R. B. Heckendorn, “The island model genetic algorithm: On separability, population size and convergence,” *Journal of Computing and Information Technology (CIT)*, vol. 7, no. 1, pp. 33-47, 1999. http://cit.fer.hr/index.php/CIT/article/view/2919

[35] E. Cantú-Paz, *Efficient and Accurate Parallel Genetic Algorithms*. Kluwer Academic Publishers (Genetic Algorithms and Evolutionary Computation series), Boston, 2000, doi: 10.1007/978-1-4615-4369-5. https://www.schweitzer-online.de/buch/Cant-Paz/Efficient-Accurate-Parallel-Genetic-Algorithms/9780792372219/A3799325/

[36] E. Cantú-Paz, “Migration policies, selection pressure, and parallel evolutionary algorithms,” *Journal of Heuristics*, vol. 7, no. 4, pp. 311-334, 2001, doi: 10.1023/A:1011375326814. https://link.springer.com/article/10.1023/A:1011375326814

[37] Z. Skolicki and K. De Jong, “The influence of migration sizes and intervals on island models,” *Proceedings of the Genetic and Evolutionary Computation Conference (GECCO 2005), ACM*, pp. 1295-1302, 2005, doi: 10.1145/1068009.1068219. https://gpbib.cs.ucl.ac.uk/gecco2005/docs/p1295.pdf

[38] J. Lässig and D. Sudholt, “General upper bounds on the runtime of parallel evolutionary algorithms,” *Evolutionary Computation (MIT Press)*, vol. 22, no. 3, pp. 405-437, 2014, doi: 10.1162/EVCO_a_00114. https://eprints.whiterose.ac.uk/98934/1/p922-single.pdf

[39] J. Jaroš, “Multi-GPU island-based genetic algorithm for solving the knapsack problem,” *2012 IEEE Congress on Evolutionary Computation (CEC), Brisbane*, pp. 1-8, 2012, doi: 10.1109/CEC.2012.6256131. https://www.fit.vut.cz/research/result/c96925/.en

[40] B. Huang, R. Cheng, Z. Li, Y. Jin and K. C. Tan, “EvoX: A distributed GPU-accelerated framework for scalable evolutionary computation,” *IEEE Transactions on Evolutionary Computation*, vol. 29, no. 5, pp. 1649-1662, 2025, doi: 10.1109/TEVC.2024.3388550. https://arxiv.org/abs/2301.12457

**What it means for us.** Parallel evolutionary algorithms split into master-slave evaluation, island (coarse-grain) and cellular (fine-grain) models [33]; the fleet is a master-slave census wrapped around an island population on the GPU. Islands hold more diversity than one panmictic population because they converge to different optima, and separability is only part of why they win [34]; the monograph gives Markov models for the number and size of demes and the trade with solution quality [35]; migration policy is itself a selection pressure, measurable as selection intensity [36]; and the interval between migrations matters more than their size, with long intervals and few migrants best [37]. Runtime bounds show that a ring or torus still gives a large parallel speedup without raising total evaluations by more than a constant [38]; one island per GPU with individuals on warps is a measured layout [39]; and GPU evaluation of whole populations is the current standard for scale [40]. For the arena: tune the migration interval before the migrant count, send few and rarely, connect islands sparsely, count the pressure that best-replaces-worst migration adds against the gate's caution, and keep match evaluation on the device while the island logic stays small.

## Quality diversity and niches

[41] J.-B. Mouret and J. Clune, “Illuminating search spaces by mapping elites,” *arXiv preprint, arXiv:1504.04909 (cs.AI)*, 2015, doi: 10.48550/arXiv.1504.04909. https://arxiv.org/abs/1504.04909

[42] A. Cully, J. Clune, D. Tarapore and J.-B. Mouret, “Robots that can adapt like animals,” *Nature*, vol. 521, no. 7553, pp. 503-507, 2015, doi: 10.1038/nature14422. https://doi.org/10.1038/nature14422

[43] J. Lehman and K. O. Stanley, “Abandoning objectives: Evolution through the search for novelty alone,” *Evolutionary Computation*, vol. 19, no. 2, pp. 189-223, 2011, doi: 10.1162/EVCO_a_00025. https://doi.org/10.1162/EVCO_a_00025

[44] J. Lehman and K. O. Stanley, “Evolving a diversity of virtual creatures through novelty search and local competition,” *Proc. 13th Annual Conference on Genetic and Evolutionary Computation (GECCO '11), ACM*, pp. 211-218, 2011, doi: 10.1145/2001576.2001606. https://doi.org/10.1145/2001576.2001606

[45] J. K. Pugh, L. B. Soros and K. O. Stanley, “Quality Diversity: A New Frontier for Evolutionary Computation,” *Frontiers in Robotics and AI*, vol. 3, Art. no. 40, 2016, doi: 10.3389/frobt.2016.00040. https://doi.org/10.3389/frobt.2016.00040

[46] V. Vassiliades, K. Chatzilygeroudis and J.-B. Mouret, “Using Centroidal Voronoi Tessellations to Scale Up the Multidimensional Archive of Phenotypic Elites Algorithm,” *IEEE Transactions on Evolutionary Computation*, vol. 22, no. 4, pp. 623-630, 2018, doi: 10.1109/TEVC.2017.2735550. https://doi.org/10.1109/TEVC.2017.2735550

[47] A. Cully and Y. Demiris, “Quality and Diversity Optimization: A Unifying Modular Framework,” *IEEE Transactions on Evolutionary Computation*, vol. 22, no. 2, pp. 245-259, 2018, doi: 10.1109/TEVC.2017.2704781. https://doi.org/10.1109/TEVC.2017.2704781

[48] M. C. Fontaine, J. Togelius, S. Nikolaidis and A. K. Hoover, “Covariance Matrix Adaptation for the Rapid Illumination of Behavior Space,” *Proc. Genetic and Evolutionary Computation Conference (GECCO '20), ACM*, pp. 94-102, 2020, doi: 10.1145/3377930.3390232. https://doi.org/10.1145/3377930.3390232

[49] D. Gravina, A. Khalifa, A. Liapis, J. Togelius and G. N. Yannakakis, “Procedural Content Generation through Quality Diversity,” *Proc. IEEE Conference on Games (CoG), London*, 2019, doi: 10.1109/CIG.2019.8848053. https://arxiv.org/abs/1907.04053

**What it means for us.** An objective can deceive search, and rewarding behavioural novelty alone beat the objective on mazes and bipeds [43]; local competition, where an individual is judged only against its behavioural neighbours, yields more functional diversity [44]. MAP-Elites keeps the best solution in each cell of a behavioural grid [41]; a map built that way let a damaged robot pick a working behaviour in minutes [42]; and quality diversity names the goal as a collection of diverse, high-performing individuals [45]. Centroidal Voronoi cells keep the archive tractable in many behavioural dimensions [46]; the unifying framework splits any such algorithm into a container, a selection operator and score types [47]; CMA-ME fills an archive with CMA-ES emitters and more than doubled MAP-Elites on QD measures, with broader strategy diversity in Hearthstone [48]; and the games survey carries QD to content and opponents [49]. The named personas are the elites of cells over behavioural descriptors such as built, road and kills less deaths. The sources say to judge a persona against its own niche rather than the global line, to use a fixed count of Voronoi cells rather than a grid, to score that run by archive coverage and quality rather than top score alone, and that the hall of fame, the islands and the gate already map onto the container, the selection operator and the score type, so the change is a choice on each axis rather than a new trainer.

## Procedural personas and player modelling

[50] C. Holmgård, A. Liapis, J. Togelius and G. N. Yannakakis, “Evolving Personas for Player Decision Modeling,” *IEEE Conference on Computational Intelligence and Games (CIG), Dortmund*, pp. 1-8, 2014, doi: 10.1109/CIG.2014.6932911. https://mail.antoniosliapis.com/papers/evolving_personas_for_player_decision_modeling.pdf

[51] C. Holmgård, M. C. Green, A. Liapis and J. Togelius, “Automated Playtesting with Procedural Personas through MCTS with Evolved Heuristics,” *IEEE Transactions on Games*, vol. 11, no. 4, pp. 352-362, 2019, doi: 10.1109/TG.2018.2808198. https://arxiv.org/abs/1802.06881

[52] C. Holmgård, A. Liapis, J. Togelius and G. N. Yannakakis, “Monte-Carlo Tree Search for Persona Based Player Modeling,” *AAAI Conference on Artificial Intelligence and Interactive Digital Entertainment (AIIDE), Player Modeling workshop*, vol. 11, no. 5, pp. 8-14, 2015, doi: 10.1609/aiide.v11i5.12849. https://ojs.aaai.org/index.php/AIIDE/article/view/12849

[53] C. Holmgård, A. Liapis, J. Togelius and G. N. Yannakakis, “Personas versus Clones for Player Decision Modeling,” *Entertainment Computing - ICEC 2014, 13th International Conference, Sydney, Australia, LNCS vol. 8770, Springer*, pp. 159-166, 2014, doi: 10.1007/978-3-662-45212-7_20. https://hal.archives-ouvertes.fr/hal-01408517

[54] G. N. Yannakakis and J. Togelius, *Artificial Intelligence and Games*. Springer, Cham (textbook, 1st ed.), 2018, doi: 10.1007/978-3-319-63519-4. https://www.gameaibook.org

[55] G. N. Yannakakis, P. Spronck, D. Loiacono and E. André, “Player Modeling,” *Artificial and Computational Intelligence in Games, Dagstuhl Follow-Ups vol. 6, Schloss Dagstuhl*, vol. 6, pp. 45-59, 2013, doi: 10.4230/DFU.Vol6.12191.45. https://drops.dagstuhl.de/entities/document/10.4230/DFU.Vol6.12191.45 (unverified detail)

[56] A. Drachen, A. Canossa and G. N. Yannakakis, “Player Modeling using Self-Organization in Tomb Raider: Underworld,” *2009 IEEE Symposium on Computational Intelligence and Games (CIG), Milan, Italy, 7-10 Sept. 2009*, pp. 1-8, 2009, doi: 10.1109/CIG.2009.5286500. https://www.um.edu.mt/library/oar/bitstream/123456789/22900/1/CIG09_IOI.pdf

[57] L. Mugrai, F. de Mesentier Silva, C. Holmgård and J. Togelius, “Automated Playtesting of Matching Tile Games,” *2019 IEEE Conference on Games (CoG)*, pp. 1-7, 2019, doi: 10.1109/CIG.2019.8848057. https://arxiv.org/abs/1907.06570

**What it means for us.** Procedural personas are agents evolved against distinct utility weightings to stand in for archetypal ways of playing: linear perceptrons did this and generalised better than Q-learning and hand-crafted agents [50]; personas evolved from designer intuition matched clones evolved from human traces [53]; and MCTS personas with evolved heuristics rated levels for players of different preferences [52], [51]. Match-3 personas were checked against human traces in a user study [57], and self-organising maps found four player types from 1,365 players' behaviour alone [56]. The textbook and the Dagstuhl chapter give the vocabulary and the taxonomy by input, output and model [54], [55]. For us: each persona is a brain weight-set picked at a local maximum of the response surface and named; the personality toggles are one brain with several weightings; the top-down pick loses little against cloning, so cloning is the check rather than the route; a persona counts only when its trace agrees with the humans it claims to stand for; and clustering the fleet's match records by behaviour is the bottom-up check on which styles the surface holds. A fixed set of personas run over seeded matches is a census of how a map or rule change plays for each style, not only for the mean bot.

## Self-play, coevolution and population-based training

[58] W. D. Hillis, “Co-evolving parasites improve simulated evolution as an optimization procedure,” *Physica D: Nonlinear Phenomena*, vol. 42, no. 1-3, pp. 228-234, 1990, doi: 10.1016/0167-2789(90)90076-2. https://www.cse.unr.edu/~sushil/class/gas/papers/DannyHillisCoevolution.pdf

[59] C. D. Rosin and R. K. Belew, “New Methods for Competitive Coevolution,” *Evolutionary Computation*, vol. 5, no. 1, pp. 1-29, 1997, doi: 10.1162/evco.1997.5.1.1. https://doi.org/10.1162/evco.1997.5.1.1

[60] S. Y. Chong, P. Tino and X. Yao, “Measuring Generalization Performance in Coevolutionary Learning,” *IEEE Transactions on Evolutionary Computation*, vol. 12, no. 4, pp. 479-505, 2008, doi: 10.1109/TEVC.2007.907593. https://research.birmingham.ac.uk/en/publications/measuring-generalization-performance-in-co-evolutionary-learning/

[61] S. Samothrakis, S. M. Lucas, T. P. Runarsson and D. Robles, “Coevolving Game-Playing Agents: Measuring Performance and Intransitivities,” *IEEE Transactions on Evolutionary Computation*, vol. 17, no. 2, pp. 213-226, 2013, doi: 10.1109/TEVC.2012.2208755. https://repository.essex.ac.uk/4121/

[62] D. Silver, T. Hubert, J. Schrittwieser, I. Antonoglou, M. Lai, A. Guez, M. Lanctot, L. Sifre, D. Kumaran, T. Graepel, T. Lillicrap, K. Simonyan and D. Hassabis, “A general reinforcement learning algorithm that masters chess, shogi, and Go through self-play,” *Science*, vol. 362, no. 6419, pp. 1140-1144, 2018, doi: 10.1126/science.aar6404. https://discovery.ucl.ac.uk/id/eprint/10069050/

[63] M. Jaderberg, V. Dalibard, S. Osindero, W. M. Czarnecki, J. Donahue, A. Razavi, O. Vinyals, T. Green, I. Dunning, K. Simonyan, C. Fernando and K. Kavukcuoglu, “Population Based Training of Neural Networks,” *arXiv preprint arXiv:1711.09846*, 2017, doi: 10.48550/arXiv.1711.09846. https://arxiv.org/abs/1711.09846v2

[64] M. Jaderberg, W. M. Czarnecki, I. Dunning, L. Marris, G. Lever, A. G. Castaneda, C. Beattie, N. C. Rabinowitz, A. S. Morcos, A. Ruderman, N. Sonnerat, T. Green, L. Deason, J. Z. Leibo, D. Silver, D. Hassabis, K. Kavukcuoglu and T. Graepel, “Human-level performance in 3D multiplayer games with population-based reinforcement learning,” *Science*, vol. 364, no. 6443, pp. 859-865, 2019, doi: 10.1126/science.aau6249. https://discovery.ucl.ac.uk/id/eprint/10076318

[65] O. Vinyals, I. Babuschkin, W. M. Czarnecki, M. Mathieu, A. Dudzik, J. Chung, D. H. Choi, R. Powell, T. Ewalds, P. Georgiev, J. Oh, D. Horgan, M. Kroiss, I. Danihelka, A. Huang, L. Sifre, T. Cai, J. P. Agapiou, M. Jaderberg, A. S. Vezhnevets, R. Leblond, T. Pohlen, V. Dalibard, D. Budden, Y. Sulsky, J. Molloy, T. L. Paine, C. Gulcehre, Z. Wang, T. Pfaff, Y. Wu, R. Ring, D. Yogatama, D. Wunsch, K. McKinney, O. Smith, T. Schaul, T. Lillicrap, K. Kavukcuoglu, D. Hassabis, C. Apps and D. Silver, “Grandmaster level in StarCraft II using multi-agent reinforcement learning,” *Nature*, vol. 575, no. 7782, pp. 350-354, 2019, doi: 10.1038/s41586-019-1724-z. https://www.nature.com/articles/s41586-019-1724-z

**What it means for us.** Competitive coevolution began with parasites whose fitness is the hosts' failure, which kept a search off local maxima [58]; the hall of fame, competitive fitness sharing and shared sampling test a new individual against the best of every past generation so progress is not lost against old opponents [59]. Generalisation of a coevolved strategy is its mean result against random test opponents, with a bound on how many samples that estimate needs [60], and intransitive relations make coevolution cycle and yield weaker players unless measured and reduced [61]. AlphaZero replaces weights only after a proved win in an evaluation match [62]; population based training copies the strong and perturbs them within one budget [63]; thirty agents trained as each other's teammates and opponents reached human level in Capture the Flag [64]; and AlphaStar's league of main agents and exploiters, seeded by imitation, reached Grandmaster [65]. Our gate is the evaluator step, and the line proved against main is a hall of fame of one; the sources say a candidate must also beat older opponents. The night's search that turned cycle off is the intransitivity case, which wants a diagnostic and an anchor outside the current population. Exploiters whose only job is to find main's weakness, and teammates drawn from a population rather than one fixed partner, are the models for the gauntlets and the wingman.

## Imitation and behaviour cloning

[66] D. A. Pomerleau, “ALVINN: An Autonomous Land Vehicle in a Neural Network,” *Advances in Neural Information Processing Systems 1 (NIPS 1988), D. S. Touretzky (ed.), Morgan Kaufmann*, pp. 305-313, 1989. https://proceedings.neurips.cc/paper/1988/hash/812b4ba287f5ee0bc9d43bbf5bbe87fb-Abstract.html

[67] S. Ross and J. A. Bagnell, “Efficient Reductions for Imitation Learning,” *Proceedings of the 13th International Conference on Artificial Intelligence and Statistics (AISTATS), PMLR*, vol. 9, pp. 661-668, 2010. https://proceedings.mlr.press/v9/ross10a.html

[68] S. Ross, G. J. Gordon and J. A. Bagnell, “A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning,” *Proceedings of the 14th International Conference on Artificial Intelligence and Statistics (AISTATS), PMLR*, vol. 15, pp. 627-635, 2011. https://proceedings.mlr.press/v15/ross11a.html

[69] A. Hussein, M. M. Gaber, E. Elyan and C. Jayne, “Imitation Learning: A Survey of Learning Methods,” *ACM Computing Surveys*, vol. 50, no. 2, Art. no. 21, 2017, doi: 10.1145/3054912. https://doi.org/10.1145/3054912

[70] T. Osa, J. Pajarinen, G. Neumann, J. A. Bagnell, P. Abbeel and J. Peters, “An Algorithmic Perspective on Imitation Learning,” *Foundations and Trends in Robotics*, vol. 7, no. 1-2, pp. 1-179, 2018, doi: 10.1561/2300000053. https://www.nowpublishers.com/article/DownloadSummary/ROB-053

[71] D. Silver, A. Huang, C. J. Maddison, A. Guez, L. Sifre, G. van den Driessche, J. Schrittwieser, I. Antonoglou, V. Panneershelvam, M. Lanctot, S. Dieleman, D. Grewe, J. Nham, N. Kalchbrenner, I. Sutskever, T. Lillicrap, M. Leach, K. Kavukcuoglu, T. Graepel and D. Hassabis, “Mastering the game of Go with deep neural networks and tree search,” *Nature*, vol. 529, no. 7587, pp. 484-489, 2016, doi: 10.1038/nature16961. https://doi.org/10.1038/nature16961

[72] N. Justesen, M. González-Duque, D. Cabarcas, J.-B. Mouret and S. Risi, “Learning a Behavioral Repertoire from Demonstrations,” *Proceedings of the 2020 IEEE Conference on Games (CoG), Osaka, Japan*, pp. 383-390, 2020, doi: 10.1109/CoG47356.2020.9231897. https://researcher.itu.dk/en/publications/learning-a-behavioral-repertoire-from-demonstrations/

[73] J. Ortega, N. Shaker, J. Togelius and G. N. Yannakakis, “Imitating human playing styles in Super Mario Bros,” *Entertainment Computing*, vol. 4, no. 2, pp. 93-104, 2013, doi: 10.1016/j.entcom.2012.10.001. https://pure.itu.dk/en/publications/imitating-human-playing-styles-in-super-mario-bros/

**What it means for us.** Behaviour cloning began with a net regressed onto a teacher's steering [66]; plain cloning compounds its errors because the learner picks the states it later sees, giving regret quadratic in the horizon [67], and DAgger closes that by labelling the learner's own states with the teacher and refitting [68]. The survey and the monograph lay out the choices along the pipeline and the split between cloning and inverse reinforcement learning [69], [70]. AlphaGo put supervised imitation first and self-play after [71]; one cloned net can carry several styles given a behaviour descriptor as input [72]; and an evolved controller scored by likeness copied a human's style more closely than direct supervised learning [73]. Our teacher is a program that answers at any state, so DAgger is cheap: label the clone's own match traces with the brain's action and refit. The clone is scored by census and not by held-out loss alone, because the drift the theory predicts shows only in a full match; the order of the pipeline is clone first, then search; one net with a style input is an alternative to one net a persona; and likeness in census is a way to score the wingman and persona nets that the fleet already runs.

## Formation control and leader-follower

[74] J. P. Desai, J. P. Ostrowski and V. Kumar, “Modeling and Control of Formations of Nonholonomic Mobile Robots,” *IEEE Transactions on Robotics and Automation*, vol. 17, no. 6, pp. 905-908, 2001, doi: 10.1109/70.976023. https://ieeexplore.ieee.org/document/976023/

[75] T. Balch and R. C. Arkin, “Behavior-Based Formation Control for Multirobot Teams,” *IEEE Transactions on Robotics and Automation*, vol. 14, no. 6, pp. 926-939, 1998, doi: 10.1109/70.736776. https://sites.cc.gatech.edu/ai/robot-lab/online-publications/formjour.pdf

[76] R. Olfati-Saber, “Flocking for Multi-Agent Dynamic Systems: Algorithms and Theory,” *IEEE Transactions on Automatic Control*, vol. 51, no. 3, pp. 401-420, 2006, doi: 10.1109/TAC.2005.864190. https://hal.elte.hu/~vicsek/downloads/papers/flocking_tac06-engineering.pdf

[77] C. W. Reynolds, “Flocks, Herds, and Schools: A Distributed Behavioral Model,” *Computer Graphics (Proceedings of SIGGRAPH '87)*, vol. 21, no. 4, pp. 25-34, 1987, doi: 10.1145/37402.37406. https://cedric.cnam.fr/~cubaud/PROCEDURAL/reynoldsSIGGRAPH87.pdf

[78] K.-K. Oh, M.-C. Park and H.-S. Ahn, “A survey of multi-agent formation control,” *Automatica*, vol. 53, pp. 424-440, 2015, doi: 10.1016/j.automatica.2014.10.022. https://doi.org/10.1016/j.automatica.2014.10.022

[79] A. K. Das, R. Fierro, V. Kumar, J. P. Ostrowski, J. Spletzer and C. J. Taylor, “A Vision-Based Formation Control Framework,” *IEEE Transactions on Robotics and Automation*, vol. 18, no. 5, pp. 813-825, 2002, doi: 10.1109/TRA.2002.803463. https://www.cis.upenn.edu/~cjtaylor/PUBLICATIONS/pdfs/DasTRA02.pdf

[80] G. L. Mariottini, F. Morbidi, D. Prattichizzo, N. Vander Valk, N. Michael, G. J. Pappas and K. Daniilidis, “Vision-Based Localization for Leader-Follower Formation Control,” *IEEE Transactions on Robotics*, vol. 25, no. 6, pp. 1431-1438, 2009, doi: 10.1109/TRO.2009.2032975. https://doi.org/10.1109/TRO.2009.2032975

[81] H. G. Tanner, A. Jadbabaie and G. J. Pappas, “Flocking in Fixed and Switching Networks,” *IEEE Transactions on Automatic Control*, vol. 52, no. 5, pp. 863-868, 2007, doi: 10.1109/TAC.2007.895948. https://repository.upenn.edu/ese_papers/279

**What it means for us.** Boids made group motion from separation, alignment and cohesion summed with priorities over a local neighbourhood [77]; behaviour-based formation control added line, column, diamond and wedge schemas with leader, neighbour and unit-centre references, summed with goal-seeking and hazard avoidance [75]. The leader-follower formation is a lead pose, shape variables a follower and a control graph, with separation-bearing and separation-separation controllers and switching between formations [74]; a follower can keep its slot from an onboard camera alone and switch controllers by mode [79]; and bearing-only measurements make the leader's relative state observable under a stated condition [80]. Reynolds's rules alone fragment, and a navigational term toward a group objective is what holds the flock [76]; alignment and distance stabilisation still converge when the sensing graph switches, as long as it stays connected [81]; and the survey sorts schemes by whether agents sense positions, displacements or distances [78]. The wingman is a one-follower control graph whose target is a separation and bearing from the human's tank. It needs an explicit follow term weighted against the brain's fire, cover and route terms, senses given in its own frame rather than world coordinates, a switching rule for when a threat takes over from following, and a gauntlet that checks it settles whenever the human stays in view.

## RTS game AI, balance and economy

[82] S. Ontañón, G. Synnaeve, A. Uriarte, F. Richoux, D. Churchill and M. Preuss, “A Survey of Real-Time Strategy Game AI Research and Competition in StarCraft,” *IEEE Transactions on Computational Intelligence and AI in Games*, vol. 5, no. 4, pp. 293-311, 2013, doi: 10.1109/TCIAIG.2013.2286295. https://www.cs.mun.ca/~dchurchill/publications/pdf/starcraft_survey.pdf

[83] M. Buro, “Real-Time Strategy Games: A New AI Research Challenge,” *Proceedings of the 18th International Joint Conference on Artificial Intelligence (IJCAI), Morgan Kaufmann*, pp. 1534-1535, 2003. https://www.ijcai.org/Proceedings/03/Papers/265.pdf

[84] G. N. Yannakakis and J. Togelius, “A Panorama of Artificial and Computational Intelligence in Games,” *IEEE Transactions on Computational Intelligence and AI in Games*, vol. 7, no. 4, pp. 317-335, 2015, doi: 10.1109/TCIAIG.2014.2339221. https://www.um.edu.mt/library/oar/bitstream/123456789/29774/1/A_panorama_of_artificial_and_computational_intelligence_in_games_2015.pdf

[85] V. Volz, G. Rudolph and B. Naujoks, “Demonstrating the Feasibility of Automatic Game Balancing,” *Proceedings of the Genetic and Evolutionary Computation Conference (GECCO), ACM*, pp. 269-276, 2016, doi: 10.1145/2908812.2908913. https://arxiv.org/abs/1603.03795

[86] F. W. Lanchester, *Aircraft in Warfare: The Dawn of the Fourth Arm*. Constable and Company, London, 1916. https://www.math.fsu.edu/~mesterto/NewCourses/MAP5932/2016/PDF/PDF02/Lanchester1916aAircraftInWarfare.pdf

[87] M. Stanescu, N. A. Barriga and M. Buro, “Using Lanchester Attrition Laws for Combat Prediction in StarCraft,” *Proceedings of the AAAI Conference on Artificial Intelligence and Interactive Digital Entertainment (AIIDE)*, vol. 11, no. 1, pp. 86-92, 2015, doi: 10.1609/aiide.v11i1.12780. https://ojs.aaai.org/index.php/AIIDE/article/view/12780

[88] M. Preuss, T. Pfeiffer, V. Volz and N. Pflanzl, “Integrated Balancing of an RTS Game: Case Study and Toolbox Refinement,” *2018 IEEE Conference on Computational Intelligence and Games (CIG), Maastricht*, pp. 1-8, 2018, doi: 10.1109/CIG.2018.8490426. https://www.semanticscholar.org/paper/aa1a6ea409a416533ad8ccc919e441e209053e68

[89] K. Rogers, V. Le Claire, J. Frommel, R. L. Mandryk and L. E. Nacke, “Using Evolutionary Algorithms to Target Complexity Levels in Game Economies,” *IEEE Transactions on Games*, vol. 15, no. 1, pp. 56-66, 2023, doi: 10.1109/TG.2023.3238163. https://www.dare.uva.nl/id/46d00463-6a48-4ea1-af8d-6a4cb1dd725b

**What it means for us.** RTS games were set as an AI challenge by their resource management, uncertainty, spatial and temporal reasoning, collaboration and opponent modelling [83]; the StarCraft survey splits the problem into strategy, tactics and reactive control and proves bots by many matches in competition [82]; and the panorama places behaviour learning, player modelling, AI-assisted design and games as benchmarks on one map [84]. Lanchester's square law says fighting strength under aimed fire scales with the square of numbers times per-unit effectiveness [86], and a generalised Lanchester model fit to simulated battles predicts outcomes well enough for a bot to decide attack or retreat on it [87]. Balancing has been done as multi-objective evolutionary search over simulated play [85], applied with a human reading the result to a real RTS [88], and economies have been generated as resource graphs evolved toward a target complexity [89]. For us: locking physical constants to ranges and balancing ballistics, drone speed and the economy is a search over censuses with a vector of objectives, read by a person before it lands, as the line already does; a Lanchester fit from census records is a cheap engage-or-hold predictor for the brain and the escort; and the logistics layer is a resource graph the fleet can search over, with the finite-resource rule as an objective.

## Curriculum and evaluation protocol

[90] Y. Bengio, J. Louradour, R. Collobert and J. Weston, “Curriculum Learning,” *Proceedings of the 26th International Conference on Machine Learning (ICML)*, pp. 41-48, 2009, doi: 10.1145/1553374.1553380. https://mlanthology.org/icml/2009/bengio2009icml-curriculum

[91] S. Narvekar, B. Peng, M. Leonetti, J. Sinapov, M. E. Taylor and P. Stone, “Curriculum Learning for Reinforcement Learning Domains: A Framework and Survey,” *Journal of Machine Learning Research*, vol. 21, no. 181, pp. 1-50, 2020. https://jmlr.org/papers/v21/20-212.html

[92] P. Henderson, R. Islam, P. Bachman, J. Pineau, D. Precup and D. Meger, “Deep Reinforcement Learning That Matters,” *Proceedings of the AAAI Conference on Artificial Intelligence (AAAI-18)*, vol. 32, no. 1, pp. 3207-3214, 2018, doi: 10.1609/aaai.v32i1.11694. https://ojs.aaai.org/index.php/AAAI/article/view/11694

[93] M. C. Machado, M. G. Bellemare, E. Talvitie, J. Veness, M. J. Hausknecht and M. Bowling, “Revisiting the Arcade Learning Environment: Evaluation Protocols and Open Problems for General Agents,” *Journal of Artificial Intelligence Research*, vol. 61, pp. 523-562, 2018, doi: 10.1613/jair.5699. https://jair.org/index.php/jair/article/view/11182

[94] R. Agarwal, M. Schwarzer, P. S. Castro, A. Courville and M. G. Bellemare, “Deep Reinforcement Learning at the Edge of the Statistical Precipice,” *Advances in Neural Information Processing Systems 34 (NeurIPS 2021), outstanding paper*, vol. 34, pp. 29304-29320, 2021. https://neurips.cc/virtual/2021/oral/26713

[95] C. Colas, O. Sigaud and P.-Y. Oudeyer, “How Many Random Seeds? Statistical Power Analysis in Deep Reinforcement Learning Experiments,” *arXiv preprint 1806.08295 (also HAL hal-01890154)*, 2018. https://arxiv.org/abs/1806.08295v2

[96] J. Goodman, D. Perez-Liebana and S. M. Lucas, “Seeding for Success: Skill and Stochasticity in Tabletop Games,” *IEEE Transactions on Games*, vol. 17, no. 3, pp. 777-786, 2025, doi: 10.1109/TG.2025.3542263. https://arxiv.org/abs/2503.02686v1

[97] D. Perez-Liebana, J. Liu, A. Khalifa, R. D. Gaina, J. Togelius and S. M. Lucas, “General Video Game AI: A Multitrack Framework for Evaluating Agents, Games, and Content Generation Algorithms,” *IEEE Transactions on Games*, vol. 11, no. 3, pp. 195-214, 2019, doi: 10.1109/TG.2019.2901021. https://ieeexplore.ieee.org/document/8664126

**What it means for us.** Ordering examples from easy to hard speeds convergence and can reach better minima [90], and the RL survey sorts curricula by how tasks are generated, sequenced and transferred, noting most are still hand-built [91]. Seeds, hyperparameters and code base move deep RL results by more than many claimed gains, and five seeds cannot separate them [92]; one benchmark's protocols drifted until results stopped comparing, and a fixed protocol with injected stochasticity and whole-run reporting was the repair [93]; point estimates over a few runs mislead, and interval estimates, the interquartile mean and performance profiles are the prescription [94]; the number of seeds follows from a wanted effect and the measured variance by a power calculation [95]; separating the game seed from the agent seeds measures how much of an outcome is the seed [96]; and a competition framework scores agents on unseen levels under a fixed budget with the ranking rule published first [97]. The gauntlets should run from one opponent on open ground to a full economy on a crowded map, with a check that weights proved on one carry to the next. The census should be sized from the floors and the measured seed variance rather than by habit, keep map and spawn seeds apart from bot seeds and pair candidates on the same set, report an interval and an IQM rather than a mean, and run under one written protocol so lines, generations and the arena compare on the same terms.

## Network width, depth and small controllers

[98] K. Hornik, M. Stinchcombe and H. White, “Multilayer feedforward networks are universal approximators,” *Neural Networks*, vol. 2, no. 5, pp. 359-366, 1989, doi: 10.1016/0893-6080(89)90020-8. https://cognitivemedium.com/magic_paper/assets/Hornik.pdf

[99] G. Cybenko, “Approximation by superpositions of a sigmoidal function,” *Mathematics of Control, Signals and Systems*, vol. 2, no. 4, pp. 303-314, 1989, doi: 10.1007/BF02551274. https://doi.org/10.1007/BF02551274

[100] Z. Lu, H. Pu, F. Wang, Z. Hu and L. Wang, “The Expressive Power of Neural Networks: A View from the Width,” *Advances in Neural Information Processing Systems 30 (NeurIPS 2017)*, vol. 30, pp. 6231-6239, 2017. https://arxiv.org/abs/1709.02540

[101] M. Raghu, B. Poole, J. Kleinberg, S. Ganguli and J. Sohl-Dickstein, “On the Expressive Power of Deep Neural Networks,” *Proceedings of the 34th International Conference on Machine Learning (ICML), PMLR*, vol. 70, pp. 2847-2854, 2017. https://proceedings.mlr.press/v70/raghu17a.html

[102] A. Gaier and D. Ha, “Weight Agnostic Neural Networks,” *Advances in Neural Information Processing Systems 32 (NeurIPS 2019)*, vol. 32, pp. 5365-5379, 2019. https://papers.neurips.cc/paper_files/paper/2019/hash/e98741479a7b998f88b8f8c9f0b6b6f1-Abstract.html

[103] D. Ha and J. Schmidhuber, “Recurrent World Models Facilitate Policy Evolution,” *Advances in Neural Information Processing Systems 31 (NeurIPS 2018)*, vol. 31, 2018. https://proceedings.neurips.cc/paper_files/paper/2018/file/2de5d16682c3c35007e4e92982f1a2ba-Paper.pdf

[104] H. Mania, A. Guy and B. Recht, “Simple random search of static linear policies is competitive for reinforcement learning,” *Advances in Neural Information Processing Systems 31 (NeurIPS 2018)*, vol. 31, 2018. https://papers.nips.cc/paper/2018/hash/7634ea65a4e6d9041cfd3f7de18e334a-Abstract.html

**What it means for us.** One hidden layer of squashing units approximates any Borel-measurable function on a compact set given enough units [98], [99], so any shortfall in the transform is width or training, not the class. For ReLU nets the floor is width n+4 for n inputs, below which almost all functions are out of reach [100]; expressivity grows exponentially with depth and polynomially with width, and the earliest weights move the function most [101]. Minimal networks scored with a shared random weight solve control tasks through their wiring alone [102]; a compact linear controller evolved by CMA-ES over learned features reached state of the art on car racing [103]; and random search over static linear policies matched deep RL at a fraction of the compute while varying across hundreds of seeds [104]. With 133 senses in, a hidden width of 64 is below the ReLU universality floor, so widening past about 137 is the first move and a third layer the second; per-layer step sizes should allow that the first layer moves the policy most; and the programmed brain as structure with a small learned residual over hand-built senses is the split these results favour.

## Ballistics and small UAV performance

[105] R. L. McCoy, *Modern Exterior Ballistics: The Launch and Flight Dynamics of Symmetric Projectiles*. Schiffer Publishing (book, 2nd ed., 328 pp., ISBN 9780764338250), 2009. https://schifferbooks.com/products/modern-ext-ballistics-2

**What it means for us.** The exterior-ballistics text builds the trajectory from the vacuum point mass through drag, wind, flat-fire approximations and the modified point-mass model [105]. For the scale system this gives metres a tile and time of flight for direct and indirect fire from a muzzle speed and elevation, so the locked ranges for shot speed, elevation and flight time can be ones a real projectile obeys. Drone speed has no source in this list and stays a design choice until one is found.

## Human-automation interaction and adjustable autonomy

[106] R. Parasuraman, T. B. Sheridan and C. D. Wickens, “A model for types and levels of human interaction with automation,” *IEEE Transactions on Systems, Man, and Cybernetics - Part A: Systems and Humans*, vol. 30, no. 3, pp. 286-297, 2000, doi: 10.1109/3468.844354. https://ieeexplore.ieee.org/document/844354

**What it means for us.** Automation is a matter of degree applied separately to information acquisition, analysis, decision selection and action implementation, with workload, situation awareness, complacency and skill degradation as the criteria for choosing a level [106]. Each goal and personality toggle in human-with-bots play is a chosen level on one of those four functions (who picks the goal, who picks the target, who fires), and the testing plan can measure whether a toggle helps the human or only offloads them by those four criteria.
