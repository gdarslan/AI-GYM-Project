# Coach evaluation summary

| model       | prompt   |   answers |   expected fact found % |   forbidden content % |   field-name leak % |   avg seconds |   scored | correct (0-2)   | relevant (0-2)   | no_invention (0-2)   | safe (0-2)   |
|:------------|:---------|----------:|------------------------:|----------------------:|--------------------:|--------------:|---------:|:----------------|:-----------------|:---------------------|:-------------|
| llama3.2-3b | v1       |        26 |                      62 |                     8 |                   8 |           0.9 |        0 |                 |                  |                      |              |
| llama3.2-3b | v2       |        26 |                      58 |                     0 |                  12 |           0.8 |        0 |                 |                  |                      |              |
| llama3.2-3b | v3       |        26 |                      88 |                     8 |                   0 |           0.7 |        0 |                 |                  |                      |              |
