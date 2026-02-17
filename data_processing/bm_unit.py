class BMUnit:
    def __init__(self, bmu_id, bid_offer_pairs_submitted, factual_acceptance_volume_by_pair, physical_volumes):
        self.unit_id = bmu_id
        self.bid_offer_pairs_submitted = bid_offer_pairs_submitted
        self.factual_acceptance_volume_by_pair = factual_acceptance_volume_by_pair
        self.physical_volumes = physical_volumes
        self.remaining_volume_by_pair = self.get_remaining_volume_by_pair()
    
    #Aim of this method is to respect MELS and MILS
    def get_remaining_volume_by_pair(self):
        remaining_volume_by_pair = {}
        positive_pair_ids = sorted([pair_id for pair_id in self.bid_offer_pairs_submitted.keys() if pair_id > 0])
        negative_pair_ids = sorted([pair_id for pair_id in self.bid_offer_pairs_submitted.keys() if pair_id < 0], reverse=True)
        max_energy_export = self.physical_volumes['MELS']
        max_energy_import = self.physical_volumes['MILS']
        scheduled_energy_delivery = self.physical_volumes['PN']
        for pair_index in range(len(positive_pair_ids)):
            energy_from_previous_offers = sum([self.bid_offer_pairs_submitted[pair_id]['level_from'] for pair_id in positive_pair_ids[:pair_index]])/2
            available_energy_this_offer = self.bid_offer_pairs_submitted[positive_pair_ids[pair_index]]['level_from']/2
            total_offer_energy_used = self.factual_acceptance_volume_by_pair[positive_pair_ids[pair_index]] if positive_pair_ids[pair_index] in self.factual_acceptance_volume_by_pair else 0
            
            total_energy_delivered = energy_from_previous_offers + scheduled_energy_delivery
            total_stated_deliverable_energy_this_bid = total_energy_delivered + available_energy_this_offer
            total_physically_deliverable_energy = min(total_stated_deliverable_energy_this_bid, max_energy_export)
            
            available_volume = max(total_physically_deliverable_energy - (total_offer_energy_used + total_energy_delivered), 0)
            remaining_volume_by_pair[positive_pair_ids[pair_index]] = available_volume
            
        for pair_index in range(len(negative_pair_ids)):
            energy_from_previous_bids = sum([self.bid_offer_pairs_submitted[pair_id]['level_from'] for pair_id in negative_pair_ids[:pair_index]])/2
            available_energy_this_bid = self.bid_offer_pairs_submitted[negative_pair_ids[pair_index]]['level_from']/2
            total_bid_energy_used = self.factual_acceptance_volume_by_pair[negative_pair_ids[pair_index]] if negative_pair_ids[pair_index] in self.factual_acceptance_volume_by_pair else 0
            
            total_energy_delivered = energy_from_previous_bids + scheduled_energy_delivery
            total_stated_deliverable_energy_this_bid = total_energy_delivered + available_energy_this_bid
            total_physically_deliverable_energy = max(total_stated_deliverable_energy_this_bid, max_energy_import)
            
            available_volume = min(total_physically_deliverable_energy - (total_bid_energy_used + total_energy_delivered), 0)
            remaining_volume_by_pair[negative_pair_ids[pair_index]] = available_volume
        
        return remaining_volume_by_pair
    