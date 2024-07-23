import os
from os import path
import argparse
import re
import read_data as rd
import taxonomy as tx
import pandas as pd
import pickle
import sys


def create_coverage_outllier_table(file_prefix, min_freq):
    mapping_units = rd.ReadDataMM(file_prefix, min_freq)
   
    mapping_units.load_coverage()
    outlier_dict = {}
    
    #read_data = rd.ReadData()
    tax_dict = tx.TaxDict()
    
    unique_id_count = 0
    unit_identity_dict = {}
    non_outlier_genus_dict = {}
    for idx, level, unit, read_i, identitiy_score, length in mapping_units.mapping_units.itertuples():
        current_id_label = unit
        matches = re.findall("kraken:taxid\\|(x?\\d+)\\|", current_id_label)
        id = str(matches[0])
        if id not in unit_identity_dict:
            unique_id_count += 1
            unit_identity_dict[id] = []
        unit_identity_dict[id].append(identitiy_score)
    print("Number of unique ids: ", unique_id_count)
        
    outliers = []
    mapping_units.filter_sig_bin_outliers(3, True)

    for id in mapping_units.filtered_tax_ids.keys():
        if mapping_units.tax_id_is_outlier[id]:
            outliers.append(id)
            if id not in outlier_dict:
                outlier_dict[id] = True

    print("Number of outliers: ", len(outlier_dict))
    # for unit in unit_identity_dict:
    #     id = unit
    #     genus_id = tax_dict.id_2_level_id(id, "genus")
    #     if id in outlier_dict:
    #         if genus_id in non_outlier_genus_dict:
    #             outlier_dict.pop(id)

    outliers = list(outlier_dict.keys())
    # print("Number of outliers after filtering: ", len(outliers))
            
            
    iter = 0
    # Create text file with outliers
    with open(".ignoreids", "w") as f:
        for outlier in outliers:
            iter += 1
            f.write(str(outlier) + "\n")
    print(iter, "outliers written to .ignoreids")
    
    
def get_coverage_outllier_list(file_prefix) -> list:
    mapping_units = rd.ReadDataMM(file_prefix, 0.0)
   
    mapping_units.load_coverage()
    mapping_units.filter_sig_bin_outliers(3, True)
    
    outliers = []
    for id in mapping_units.filtered_tax_ids.keys():
        if mapping_units.tax_id_is_outlier[id]:
            outliers.append(id)
            
    return outliers


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Outlier detection", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-mtsv", "--mtsv-file",  type=str, help="MTSV File")
    parser.add_argument("-mtsvl", "--mtsv-lookup-file",  type=str, help="MTSV Lookup File")
    parser.add_argument("-meta", "--meta-maps-file",  type=str, help="MetaMaps File")
    parser.add_argument("-metaref", "--meta-maps-reference-file", type=str, help="MetaMaps file to filter MTSV with")
    parser.add_argument("-mtsvref", "--mtsv-reference-file", type=str, help="MTSV file to filter MetaMaps reads with")
    parser.add_argument("-s", "--seed", type=int, help="Seed for random number generator", default=0)
    parser.add_argument("-f", "--min-frequency", type=float, help="Minimum frequency of taxon label to plot", default=0.0)
    parser.add_argument("-a", "--alias", type=str, help="Alias for file", default=None)
    parser.add_argument("-C", "--clear", action="store_true", help="DANGER! Clears all files in reads directory") # DANGEROUS?
    parser.add_argument("-B", "--sig-bin", action="store_true", help="Enable sig-bin filtering (METAMAPS ONLY)", default=False)
    parser.add_argument("-r", "--rare", type=int, help="Rareify to given read count", default=None)
    
        
    args = parser.parse_args()
    config = vars(args)
    min_freq = config["min_frequency"]
    seed = config["seed"]
    
    mtsv_file = config["mtsv_file"]
    mtsv_lookup_file = config["mtsv_lookup_file"]
    meta_maps_file = config["meta_maps_file"]
    meta_maps_reference_file = config["meta_maps_reference_file"]
    mtsv_reference_file = config["mtsv_reference_file"]
    
    clear = config["clear"]
    sig_bin = config["sig_bin"]
    alias = config["alias"]
    rare = config["rare"]
    
    mtsv_present = (mtsv_file and mtsv_lookup_file)
    meta_present = (meta_maps_file)
    
    name = ""
    
    if mtsv_present and meta_present:
        sys.exit("Only one of MTSV or MetaMaps files can be present")
    
    if not mtsv_present and not meta_present:
        sys.exit("One of MTSV or MetaMaps files must be present")
    
    if not meta_maps_file and mtsv_file and not mtsv_lookup_file:
        sys.exit("MTSV lookup file must be present")
        
    
    read_data = rd.ReadData()
    
    if mtsv_file and mtsv_lookup_file:
        name = path.basename(mtsv_file)
        read_data.parse_mtsv_reads(mtsv_file, mtsv_lookup_file)
        read_data.resolve_lca()
        if meta_maps_reference_file:
            # Incidence filter
            read_data.parse_metamaps_reads_2_taxon(meta_maps_reference_file, True)
            read_data.prune_non_incidental_reads()
    elif meta_maps_file:
        name = path.basename(meta_maps_file)
        read_data.parse_metamaps_reads_2_taxon(meta_maps_file)
        if mtsv_reference_file:
            # Incidence filter
            read_data.parse_mtsv_reads_2_taxon(mtsv_reference_file, True)
            read_data.prune_non_incidental_reads()
    
    if alias is not None:
        name = alias
            
    # sig bin filter
    if meta_present and sig_bin:
        sig_bin_file = path.splitext(os.path.basename(meta_maps_file))[0]
        sig_bin_file = path.splitext(os.path.basename(sig_bin_file))[0]
        sig_bin_file_path = path.dirname(meta_maps_file)
        sig_bin_file = path.join(sig_bin_file_path, sig_bin_file)
        outlier_list = get_coverage_outllier_list(sig_bin_file)
        outlier_dict = {}
        for outlier in outlier_list:
            outlier_dict[outlier] = True
        print("DISCARDING OUTLIERS")
        i = 0
        keys = list(read_data.reads.keys())
        for read in keys:
            currents_read = read_data.reads[read]
            if currents_read.assigned_taxon_id in outlier_dict:
                i += 1
                read_data.reads.pop(read)
        print(i, "outliers discarded")
    
    
    # frequency filter TODO: LOW PRIORITY
    
    # rareify
    if rare:
        read_data.rarefy(rare, seed)
    
    
    # pickle reads
    currents_reads = read_data.reads
    processed_read_count = read_data.processed_read_count
    
    if clear:
        for file in os.listdir("reads"):
            file_path = os.path.join("reads", file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(e)
    
    if not os.path.exists("reads"):
        os.makedirs("reads")
     
    pickle.dump((currents_reads, processed_read_count), open("reads/" + name + ".p", "wb"))
    print(len(read_data.reads), "reads pickled to reads/" + str(name) + ".p")
    