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

        expected_keys = "uuid signal1 signal2 coloc_h3 coloc_h4 cross_signal n_coloc_between_traits".split()
        for key in expected_keys:
            assert key in response.data["results"][0]

        assert response.status_code == HTTP_200_OK

    def test_gene(self):
        self.url = reverse('api:coloc-all')
        response = self.client.get(self.url, data={"genes": "ST6GAL1"}, format="json")

        expected_keys = "uuid signal1 signal2 coloc_h3 coloc_h4 cross_signal n_coloc_between_traits".split()
        for key in expected_keys:
            assert key in response.data["results"][0]

        assert response.data["results"][0]["signal2"]["analysis"]["trait"]["gene"]["symbol"] == "ST6GAL1"

        assert response.status_code == HTTP_200_OK

    def test_signal1_trait(self):
        self.url = reverse('api:coloc-all')

        region = "3:186665644-186665645"

        data = {
            "signal1_analysis": "gwas_diamante_t2d_eur",
            "signal1_region": region,
            "min_h4": 0.5,
            "min_r2": 0.3,
            "signal1_min_logp": 0,
            "signal2_min_logp": 0,
        }

        response = self.client.get(self.url, data=data, format="json")

        expected_keys = "uuid signal1 signal2 coloc_h3 coloc_h4 cross_signal n_coloc_between_traits".split()
        for key in expected_keys:
            assert key in response.data["results"][0]

        assert response.data["results"][0]["signal1"]["analysis"]["trait"]["uuid"] == "T2D"
        assert response.data["results"][0]["signal1"]["analysis"]["uuid"] == "gwas_diamante_t2d_eur"

        assert response.status_code == HTTP_200_OK

    def test_analysis_uuid(self):
        self.url = reverse('api:coloc-all')

        data = {
            "analyses": "gwas_diamante_t2d_eur",
            "min_h4": 0.5
        }

        response = self.client.get(self.url, data=data, format="json")

        expected_keys = "uuid signal1 signal2 coloc_h3 coloc_h4 cross_signal n_coloc_between_traits".split()
        for key in expected_keys:
            assert key in response.data["results"][0]

        assert response.data["results"][0]["signal1"]["analysis"]["uuid"] == "gwas_diamante_t2d_eur"

        assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
class TestColocResultDetailView(APITestCase):
    def test_simple(self):
        self.params = {
            'uuid': "F3NhnTvjunBzffcBYTR8XS",
        }
        self.url = reverse('api:coloc-detail', kwargs=self.params)
        response = self.client.get(self.url, format="json")

        expected_keys = "uuid signal1 signal2 coloc_h3 coloc_h4 cross_signal n_coloc_between_traits".split()
        for key in expected_keys:
            assert key in response.data

        analysis_keys = "uuid analysis_type genome_build trait study publication ld external_link".split()
        for key in analysis_keys:
            assert key in response.data["signal1"]["analysis"]
            assert key in response.data["signal2"]["analysis"]

        signal_keys = ("uuid analysis lead_variant neg_log_p effect_cond effect_marg cond_minp_variant").split()
        for key in signal_keys:
            assert key in response.data["signal1"]
            assert key in response.data["signal2"]

        trait_keys = "uuid biomarker_type".split()
        for key in trait_keys:
            assert key in response.data["signal1"]["analysis"]["trait"]
            assert key in response.data["signal2"]["analysis"]["trait"]

        assert response.data["uuid"] == "F3NhnTvjunBzffcBYTR8XS"
        assert response.data["signal2"]["analysis"]["trait"]["gene"]["symbol"] == "ST6GAL1"

        assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
class TestLDStatsRegionView(APITestCase):
    def test_simple(self):
        self.params = {
            'uuid': "ukbb_grch37_all_muscislet",
        }
        self.data = {
            'chrom': '3',
            'start': 186655645,
            'end': 186675645,
            'variant': "3:186665645_C/T"
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
class TestFinemappedSignalSummRegionView(APITestCase):
    def test_simple(self):
        self.params = {
            'uuid': "LkCCTQ4hwMcu5bKcen7nGC",
        }
        self.data = {
            'chrom': '1',
            'start': 117532790 - 10000,
            'end': 117532790 + 10000,
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
        self.url = reverse('api:analysis-manhattan', kwargs=self.params)
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
