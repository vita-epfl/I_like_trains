import random
from common.base_agent import BaseAgent
from common.move import Move


class Agent(BaseAgent):

    ''' Beginning of the code:
    We define the methods used to decide the move before the method get_move (see bellow).'''

    def main_path(self):
        '''This method will determine the "main strategy": it will decide the next main "target",
        and returns 2 directions (among up, down, left or right) corresponding to the moves the
        train has to do in the future to reach it.'''
        
        #toutes les infos sur notre train
        train = self.all_trains[self.nickname]
        
        
        
        # We rename the variables we'll call in the method to simplify the syntax
        # TODO Trouver les path de chacune des variables ci-dessous
        # /!\ Les loc doivent être données tq 1 case == 1 valeur (diviser nbr pixels par la taille des cellules)
        self.opponent_loc = ...
        self.opponent_head = ...
        zone_loc = ...
        passen1_loc = ...
        passen1_value = ...
        passen2_loc = ...
        passen2_value = ...
        # Our own attributes
        self.cur_dir = Move(tuple(train["direction"])) # Must be precisely "up", "down", "left" or "right"
        pass
        our_len = ...
        self.our_loc = ...
        self.our_head = tuple(train["position"])
        # Calculus of the distances ("d")
        d_passen1 = ...
        d_passen2 = ...
        d_oppo_passen1 = ...
        d_oppo_passen2 = ...
        d_zone = ...
        # We also create new variables to help us "making choices". It will give to each parameter
        # that can have an importance in our choice a "weight". (here, "c" means "coefficient")
        # /!\ This part will have to be adapted by experiments ! '''
        c_len = ...
        c_passen_val = ...
        c_d_zone = ...
        c_d_passen = ...
        c_d_oppo_passen = ...


        ''' Beginning of the method: we'll compact the parameters into two variables: one for each
        "target a passenger" choice, and one for the "target zone" choice.
        
        TODO Il manque une condition "train_in_zone", où il faut adapter le comportement du train.'''
        
        # Deciding section:
        # 2 parameters can affect our choice to target the zone: our current length, and the distance with it.
        weight_zone = (c_d_zone * d_zone) + (c_len * our_len)
        # Three parameters to target a passenger: their distance, value and the distance with the opponent's head.
        weight_passen1 = (c_d_passen * d_passen1) + (c_passen_val * passen1_value) - (c_d_oppo_passen * d_oppo_passen1)
        weight_passen2 = (c_d_passen * d_passen2) + (c_passen_val * passen2_value) - (c_d_oppo_passen * d_oppo_passen2)
        if weight_passen1 > weight_passen2:
            if weight_passen1 > weight_zone:
                self.target = passen1_loc
        elif weight_passen2 > weight_zone:
            self.target = passen2_loc
        else:
            self.target = zone_loc # Prendre le point le plus proche (OU le plus dans le coin) de la liste.
        
        
        # Determining-directions' section:
        # TODO Compléter la section ci dessous de sorte à donner les bons output
        if self.our_head[0] - self.target[0] < 0:
            if self.our_head[1] - self.target[1] < 0:
                return ("","")
            elif self.our_head[1] - self.target[1] > 0:
                return ("","")
            else:                # self.our_head[1] - self.target[1] == 0
                return ("",None)

        elif self.our_head[0] - self.target[0] > 0:
            if self.our_head[1] - self.target[1] < 0:
                return ("","")
            elif self.our_head[1] - self.target[1] > 0:
                return ("","")
            else:
                return ("",None)
        
        else:                     # self.our_head[0] - self.target[0] == 0
            if self.our_head[1] - self.target[1] < 0:
                return ("",None)
            else:                 # self.our_head[1] - self.target[1] > 0
                return ("",None)
        # On ne peut pas avoir 2 None: le code doit etre construit de sorte à ce que lorsqu'on a
        # atteint target, ce dernier s'actualise, et vise un autre point.'''        

        # FIN DE MAIN_PATH


    def adapt_path(self, directions): 
        '''This method is used to change / chose among the directions given by main_path
        if there is a "danger" on the way. It will have the "last word" to decide which
        way to go. The input "directions" is a 2-elements tuple among "up", "down", "right",
        "left" and / or None (in case the target is in a "straight" direction).'''

        '''TODO: (dans l'ordre de "priorité" de la méthode)

        - Déterminer parmis les deux directions données, si il y en a une "prioritaire" (e.t. si une
        des directions données est derrière (voire derrière nous), et donc inateignable en 1 action)

        - Danger imminent: choisir si possible la 2eme direction, sinon une autre direction
        (qui n'est donc pas mentionnée dans "directions");
        /!\ Cette partie est nécessaire mais pas suffisante: si elle s'active (et élimine une
        direction dangereuse dans l'immédiat), mais qu'il reste à choisir entre la "deuxième direction"
        et la direction la "moins bonne", il est tout de même important de tester la suite avant de
        prendre une décision.

        - Danger potentiel: Trouver des "situations dangereuses", et la logique du
        code pour les identifier et les éviter;

        (Optionnel:)
        - Pas de danger: En cas de nullité des 2 premiers cas, trouver un "paterne idéal"
        (e.d. la suite de mouvement la plus "safe" possible) -> Idée: essayer le plus possible
        de passer vers le centre du terrain, d'où tous les points sont atteignable rapidement'''


    def get_move(self):
        """
        This method is regularly called by the client to get the next direction of the train.
        """
        self.main_path()
        moves = [Move.UP, Move.DOWN, Move.LEFT, Move.RIGHT]
        return self.cur_dir.turn_right()
        #return random.choice(BASE_DIRECTIONS) # Replace this with your own logic
