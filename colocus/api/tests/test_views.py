import json

import pytest
from django.test import TestCase  # noqa F401
from django.urls import reverse
from rest_framework.status import HTTP_200_OK
from rest_framework.test import APITestCase

from colocus.api.tests.util import is_variant, valid_alleles


@pytest.mark.django_db
class TestColocResultListView(APITestCase):
    def test_simple(self):
        self.url = reverse('api:coloc-all')
        response = self.client.get(self.url, format="json")

        expected_keys = "uuid signal1 signal2 coloc_h3 coloc_h4 analysis cross_signal n_coloc_between_traits".split()
        for key in expected_keys:
            assert key in response.data["results"][0]

        assert response.status_code == HTTP_200_OK

    def test_gene(self):
        self.url = reverse('api:coloc-all')
        response = self.client.get(self.url, data={"genes": "ATP2B4"}, format="json")

        expected_keys = "uuid signal1 signal2 coloc_h3 coloc_h4 analysis cross_signal n_coloc_between_traits".split()
        for key in expected_keys:
            assert key in response.data["results"][0]

        assert response.data["results"][0]["signal2"]["lead_variant_assoc_gene"] == "ATP2B4"

        assert response.status_code == HTTP_200_OK

    def test_signal1_trait(self):
        self.url = reverse('api:coloc-all')

        data = {
            "signal1__trait__uuid": "AsatadjBMI_UKBB_2022_hg19",
            "signal1__lead_variant_chrom": "1",
            "signal1__lead_variant_pos__gte": 203016075,
            "signal1__lead_variant_pos__lte": 204016075,
            "coloc_h4__gte": 0.5,
            "r2__gte": 0.3,
            "signal1__lead_variant_neg_log_p__gte": 0,
            "signal2__lead_variant_neg_log_p__gte": 0,
        }

        response = self.client.get(self.url, data=data, format="json")

        expected_keys = "uuid signal1 signal2 coloc_h3 coloc_h4 analysis cross_signal n_coloc_between_traits".split()
        for key in expected_keys:
            assert key in response.data["results"][0]

        assert response.data["results"][0]["signal1"]["trait"]["uuid"] == "AsatadjBMI_UKBB_2022_hg19"

        assert response.status_code == HTTP_200_OK

    def test_trait_uuid(self):
        self.url = reverse('api:coloc-all')

        data = {
            "trait_uuid": "gwas_diamante_t2d_eur",
            "coloc_h4__gte": 0.5
        }

        response = self.client.get(self.url, data=data, format="json")

        expected_keys = "uuid signal1 signal2 coloc_h3 coloc_h4 analysis cross_signal n_coloc_between_traits".split()
        for key in expected_keys:
            assert key in response.data["results"][0]

        assert response.data["results"][0]["signal1"]["trait"]["uuid"] == "gwas_diamante_t2d_eur"

        assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
class TestColocResultDetailView(APITestCase):
    def test_simple(self):
        self.params = {
            'uuid': 4293814911,
        }
        self.url = reverse('api:coloc-detail', kwargs=self.params)
        response = self.client.get(self.url, format="json")

        expected_keys = "uuid signal1 signal2 coloc_h3 coloc_h4 analysis cross_signal n_coloc_between_traits".split()
        for key in expected_keys:
            assert key in response.data

        analysis_keys = "uuid study_name study_date authors contact_email pmid label".split()
        for key in analysis_keys:
            assert key in response.data["analysis"]

        signal_keys = ("uuid trait lead_variant_chrom lead_variant_pos lead_variant_marker lead_variant_neg_log_p "
                       "lead_variant_effect lead_variant_effect_marg lead_variant_nearest_gene lead_variant_assoc_gene"
                       " lead_variant_assoc_gene_ensg lead_variant_assoc_exon cond_minp_variant").split()
        for key in signal_keys:
            assert key in response.data["signal1"]
            assert key in response.data["signal2"]

        trait_keys = "uuid label trait_type genome_build metadata ld study_name".split()
        for key in trait_keys:
            assert key in response.data["signal1"]["trait"]
            assert key in response.data["signal2"]["trait"]

        assert response.data["uuid"] == "4293814911"
        assert response.data["signal2"]["lead_variant_assoc_gene"] == "ATP2B4"

        assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
class TestLDPairsRegionView(APITestCase):
    def test_simple(self):
        self.params = {
            'uuid': "ukbb_grch37_all",
        }
        self.data = {
            'chrom': '1',
            'start': 203466075,
            'end': 203566075,
            'variant': "1:203516075_T/A"
        }
        self.url = reverse('api:ld-region', kwargs=self.params)
        response = self.client.get(self.url, data=self.data, format="json")

        expected_keys = "correlation position1 position2 variant1 variant2".split()
        for key in expected_keys:
            assert key in response.data[0]

        for rec in response.data:
            assert is_variant(rec["variant1"])
            assert is_variant(rec["variant2"])
            assert 0 <= float(rec["correlation"]) <= 1

        assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
class TestMarginalSignalSummRegionView(APITestCase):
    def test_simple(self):
        self.params = {
            'uuid': 3927258885,
        }
        self.data = {
            'chrom': '1',
            'start': 203466075,
            'end': 203566075,
        }
        self.url = reverse('api:signals-summstats', kwargs=self.params)
        response = self.client.get(self.url, data=self.data, format="json")

        expected_keys = ("chromosome position variant ref_allele alt_allele variant t1_neg_log_pvalue t1_beta "
                         "t1_stderr_beta t1_alt_allele_freq t2_neg_log_pvalue t2_beta t2_stderr_beta "
                         "t2_alt_allele_freq").split()

        for key in expected_keys:
            assert key in response.data[0]

        for rec in response.data:
            assert is_variant(rec["variant"])
            assert int(rec["position"]) >= 0
            assert valid_alleles(rec["ref_allele"])
            assert valid_alleles(rec["alt_allele"])

        assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
class TestInternalTraitManhattanView(APITestCase):
    def test_simple(self):
        self.params = {
            'uuid': "gwas_diamante_t2d_eur",
        }
        self.url = reverse('api:trait-manhattan', kwargs=self.params)
        response = self.client.get(self.url, format="json")

        # This view unfortunately returns a `http.FileResponse` which is streaming content...
        content = b''.join(response.streaming_content)
        json_data = json.loads(content.decode("utf-8"))

        unbinned_keys = "chrom pos rsid ref alt beta stderr_beta alt_allele_freq nearest_genes peak pvalue".split()
        for key in unbinned_keys:
            assert key in json_data["unbinned_variants"][0]

        assert "ensg" in json_data["unbinned_variants"][0]["nearest_genes"][0]
        assert "symbol" in json_data["unbinned_variants"][0]["nearest_genes"][0]

        binned_keys = "chrom pos qval_extents qvals".split()
        for key in binned_keys:
            assert key in json_data["variant_bins"][0]

        for extent in json_data["variant_bins"][0]["qval_extents"]:
            assert extent[0] >= 0
            assert extent[1] >= 0

        for qval in json_data["variant_bins"][0]["qvals"]:
            assert qval >= 0

        assert response.status_code == HTTP_200_OK
