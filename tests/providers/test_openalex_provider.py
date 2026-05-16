from snow.domain.models import Work
from snow.providers.openalex_provider import OpenAlexProvider


class FakeOpenAlexProvider(OpenAlexProvider):
    def __init__(self, data):
        self.data = data

    def _work_data(self, work: Work):
        return self.data


class DescribeOpenAlexEnrichment:
    def it_fills_only_missing_fields(self):
        provider = FakeOpenAlexProvider({
            "title": "Original",
            "doi": "https://doi.org/10/openalex",
            "publication_year": 2020,
            "primary_location": {
                "landing_page_url": "https://openalex.example/work",
                "source": {"display_name": "OpenAlex Venue"},
            },
            "best_oa_location": {"pdf_url": "https://openalex.example/work.pdf"},
            "abstract_inverted_index": {"Hello": [0], "world": [1]},
        })
        work = Work(
            id="x",
            bib_key="x2020",
            title="Original",
            venue="Bib Venue",
            doi="10/original",
        )

        enriched = provider.enrich_work(work)

        assert enriched.doi == "10/original"
        assert enriched.venue == "Bib Venue"
        assert enriched.url == "https://openalex.example/work"
        assert enriched.pdf_url == "https://openalex.example/work.pdf"
        assert enriched.abstract == "Hello world"

    def it_keeps_existing_url_pdf_url_and_abstract(self):
        provider = FakeOpenAlexProvider({
            "title": "Original",
            "doi": "https://doi.org/10/openalex",
            "publication_year": 2020,
            "primary_location": {
                "landing_page_url": "https://openalex.example/work",
                "source": {"display_name": "OpenAlex Venue"},
            },
            "best_oa_location": {"pdf_url": "https://openalex.example/work.pdf"},
            "abstract_inverted_index": {"OpenAlex": [0], "abstract": [1]},
        })
        work = Work(
            id="x",
            bib_key="x2020",
            title="Original",
            url="https://bib.example/work",
            pdf_url="https://bib.example/work.pdf",
            abstract="Bib abstract",
        )

        enriched = provider.enrich_work(work)

        assert enriched.url == "https://bib.example/work"
        assert enriched.pdf_url == "https://bib.example/work.pdf"
        assert enriched.abstract == "Bib abstract"
