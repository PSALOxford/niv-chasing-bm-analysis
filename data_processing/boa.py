from dataclasses import dataclass

@dataclass
class Boa:
    plant_id: str
    bid_offer_pair_id: int
    accepted_price: float