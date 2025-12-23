# Organization of QuESt PCM Results

Results are organized into a dedicated directory for each simulation run, with the directory name containing a timestamp to uniquely identify the run. Within each run directory, subdirectories are created according to the user-selected export resolution. Users may choose to export all results at once or to aggregate outputs on a daily, weekly, or monthly basis. For each selected export resolution, the results are further separated into subdirectories based on output format, including static PNG plots and interactive HTML visualizations. This structure allows users to view the results using lightweight static figures and richer, browser-based interactive results.

Within these format-specific directories, results are systematically organized by category. For example, ancillary services dispatch and clearing price results are stored in their own dedicated folders. Additionally, each energy storage system modeled in the simulation has a separate directory named after the storage asset. These storage-specific directories contain plots detailing storage dispatch behavior, operational costs, revenue streams, and state-of-charge (SoC) trajectories over the simulation horizon.
 
Overall, QuESt PCM presents simulation outputs through the following three formats:

1. Excel Summary Workbook:
A comprehensive Excel workbook that provides high-level summaries of system operation, including overall operational metrics, generation details, energy storage performance, line congestion, and line flow violations under contingency conditions.

2. Visualization Outputs (PNG and Interactive HTML):
A collection of static Matplotlib PNG figures and interactive HTML visualizations illustrating system-wide dispatch, locational marginal prices (LMPs), ancillary service dispatch, and clearing prices. In addition, detailed, storage-specific plots are generated for each energy storage system, showing dispatch behavior, operational costs, revenues, and state-of-charge (SoC) trajectories.

3. JSON Output Files:
Machine-readable JSON files containing detailed results from the day-ahead unit commitment and real-time economic dispatch simulations. These files include granular information not available in the Excel summaries or plots, such as generator commitment status, startup and shutdown decisions, dispatch levels of thermal units at each timestep, load curtailment at each bus, and transmission line flows over time. For energy storage systems, technology-specific operational details such as generator and pump schedules for pumped hydro storage are also provided.

Example: For a weekly result export resolution, QuEST PCM outputs are arranged in the directory as follows:

- TimeStamp_Folder/
    - Week1-Week2/  (or Week2-Week3, etc.)
        - Plotly_Plots/
            - Dispatch.html, Costs.html, LMP.html, ...
            - Ancillary_Services/
                - Regulation_UP.html, Clearing_Prices.html, ...
            - Storage_1/ 
                - Storage_Dispatch.html, Costs.html, Revenue.html, SoC.html
            - Storage_2/...
        - PNG_Plots/
            - Dispatch.png, Costs.png, LMP.png, ...
            - Ancillary_Services/ 
                - Regulation_UP.png, Clearing_Prices.png, ...
            - Storage_1/ 
                - Dispatch.png, Costs.png, Revenue.png, SoC.png
            - Storage_2/...
        - DA_Results.json
        - RT_Results.json
    - Summary.xlsx
    


