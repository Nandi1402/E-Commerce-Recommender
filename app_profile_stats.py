import cProfile
import pstats
import main # Your main application file

cProfile.run('main.app.run(debug=False)', 'profile_results') # Run your app with cProfile

p = pstats.Stats('profile_results')
p.sort_stats('cumulative').print_stats(20) # Print top 20 functions by cumulative time