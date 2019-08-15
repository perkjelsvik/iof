![Interactive documentation](https://img.shields.io/badge/html-Documentation-orange)

# Internet of Fish (IoF) repository

To see the original form of the repo at the time of finishing my thesis, see the commit labeled [v.1.0](https://github.com/PerKjelsvik/iof/releases/tag/1.0). If you'd rather want to explore this commit here on GitHub, instead of downloading the source code, you can explore the repo directly here, [a8afc1b068](https://github.com/PerKjelsvik/iof/tree/a8afc1b068ac4d10d8111e0d299cad41a0a26e44). I will update this readme properly after my thesis has been evaluated, but I want to keep it's original form mostly intact for now. The subsection below is the original readme description.

### Original readme from thesis submission  

This repository is the result of my final year as a master student. The development of the code was done in a private repository. Opening up the original repository would be ideal, but there are confidental data and codes in the commit history. This repository was created as a fresh starting point for further development. 

The code for back-end in this repository should be fully working and ready to go. Front-end however is only included as documentation, since the Dash apps written are custom-made for the case study of the thesis. There are also several functions for both parts that could not be included. 

Regarding documentation files in the form of html / pdf / readthedocs. Documentation was generated with sphinx, but it was done so at a stage where it included several parts that could not be included. It was also in a rough state. New documentation will be added at a later date. 

This is a bare bones version of the repository and the code. Both will be updated in the future, but first there is a vacation to take care of :-)

### Updated readme august 2019

I worked actively the two first weeks of august 2019 on developing iof further. Main goals of this period was to make the project code viable for new projects, with minimal setup. That means to remove all hardcoded metadata handling, and to make setup easier for future experiments. During the two weeks, I was able to change the database logic to filter with `sql` queries instead of keeping the processed complete dataframes in `pyarrow plasma` store. This was possible without signifcant speed loss by adding a datetime and hour column to the datbase tables. Converting timestamps to datetime and then string was the most demanding process task previously. I also made initalization of both backend end frontend simpler and possible. Positioning is now also optional, both in backend and frontend. This means that `iof` should be as easy to use for wild fish experiments and cage experiments. To make metadata preparation easier, I have made an excel sheet format that can be filled out and used. This is not extensively tested, so bugs might pop up. I have also added specific MQTT topic support, rather than subscribing to `#` by default. I have also made interactive docs for the project (available [here](https://perkjelsvik.github.io/iof)). Some code documentation has also been updated, but parts of backend is still lacking in this regard, and frontend is still not good in both structure and documentation. But it works well.

After these two weeks, I imagine there will be some updates here and there. But at this point it should be ready to use for other epxeriments with little configuration needed. I have not addressed public hosting of the appplications in any regard, but several guides exists on this aspect of having a web application. The workaround used during development was to allow specific ip-addresses to the machine running the application. Not a good or scalable solution. In any case, it's been fun developing this tool. I now hope the tool has matured enough to be used in future experiments, both commercial and research.

![alt text](https://github.com/perkjelsvik/iof/docs/source/images/webpage.png "Dash iof webpage")