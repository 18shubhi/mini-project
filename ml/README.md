# CampusFind Matching Module

This standalone Python module ranks possible matches between open LOST and FOUND
item reports. It uses TF-IDF features with cosine similarity for
the title and description, then combines that result with category, colour,
location, and date similarities.

The weighted features are normalized when structured data is missing. Colour is
inferred from a small, explainable vocabulary in the title and description;
CampusFind's current item model does not have a colour field. Scores are relative
similarity suggestions on a 0-100 scale, not measured prediction accuracy or a
guarantee that two reports refer to the same physical item.

The ML module is stateless and does not train or persist a model. TF-IDF is fit
for each source report and its eligible candidate set. Django's `matching` app
handles JWT authentication, ownership checks, database queries, and response
serialization, and calls `ml.matcher.rank_matches` for the actual ranking.

The matcher uses only Python's standard library, so it adds no packages to the
existing Django environment. Run the unit tests from the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s ml\tests -v
```