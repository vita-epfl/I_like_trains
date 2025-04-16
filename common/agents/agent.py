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
        
        """toutes les infos sur notre train, import"""
        self.train = self.all_trains[self.nickname]
        """toutes infos sur l'autre train, import"""
        self.autre = self.all_trains["Agent1"]
        
        #info sur les passagers
        passagers = self.passengers
        
        
        # We rename the variables we'll call in the method to simplify the syntax
        # TODO Trouver les path de chacune des variables ci-dessous
        # /!\ Les loc doivent être données tq 1 case == 1 valeur (diviser nbr pixels par la taille des cellules)
        """ infos sur l'autre"""
        self.opp_cur_dir = Move(tuple(self.autre["direction"])) # Must be precisely "up", "down", "left" or "right"
        self.opp_len = int(len(self.autre["wagons"]))
        self.opponent_loc = ...
        self.opponent_head = tuple(self.autre["position"])
        """ info sur delivery zone"""    
        zone_loc = [tuple(self.delivery_zone["position"])]
        znch = self.delivery_zone["height"]//20 #zone_nb_case_haut, combien de cases de haut fait la zone
        zncl = self.delivery_zone["width"]//20 #zone_nb_case_large, idem de large
        
        match znch :
            case 1:
                match zncl:
                    case 1:
                        print()
                    case _:
                        for x in range(1,zncl):
                            zone_loc.append((zone_loc[0][0]+x*20,zone_loc[0][1]))
            case _:
                match zncl:
                    case 1:
                        for y in range(1,znch):
                            zone_loc.append((zone_loc[0][0],zone_loc[0][1]+y*20))
                    case _:
                        for y in range(1,znch):
                            for x in range(1,zncl):
                                zone_loc.append((zone_loc[0][0] + x*20,zone_loc[0][1] + y*20)) # à voir si le dernier cas suffit pas, histoire de faire propre
        zone_loc_set = set(zone_loc)        
        """ info sur passagers"""
        passen1_loc = passagers[0]["position"]
        passen1_value = passagers[0]["value"]
        passen2_loc = passagers[1]["position"]
        passen2_value = passagers[1]["value"]
        """ Our own attributes"""
        self.cur_dir = Move(tuple(self.train["direction"])) # Must be precisely "up", "down", "left" or "right"
        our_len = int(len(self.train["wagons"]))
        self.our_loc = ...
        self.our_head = tuple(self.train["position"])
        """# Calculus of the distances ("d")"""
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
        way to go. Convert the "directions"-2-elements tuple (among "up", "down", "right",
        "left" and / or None) into a string (among same directions)'''

        '''TODO: (dans l'ordre de "priorité" de la méthode)

        - 1: Déterminer parmis les deux directions données, si il y en a une "prioritaire" (e.t. si une
        des directions (ou LA direction) donné.e.s est derrière nous, et donc inateignable en 1 action)

        - 2: Danger imminent: choisir si possible la 2eme direction, sinon une autre direction
        (qui n'est donc pas mentionnée dans "directions");
        /!\ Cette partie est nécessaire mais pas suffisante: si elle s'active (et élimine une
        direction dangereuse dans l'immédiat), mais qu'il reste à choisir entre la "deuxième direction"
        et la direction la "moins bonne", il est tout de même important de tester la suite avant de
        prendre une décision.

        - 3: Danger potentiel: Trouver des "situations dangereuses", et la logique du
        code pour les identifier et les éviter;

        (Optionnel:)
        - 4: Pas de danger: En cas de nullité des 3 premiers cas, trouver un "paterne idéal"
        (e.d. la suite de mouvement la plus "safe" et "optimisée" possible) -> Idée: essayer le plus
        possible de passer vers le centre du terrain, d'où tous les points sont atteignable rapidement'''


        # Partie 1: Direction prioritaire (pas de return ici) 
        if self.cur_dir not in directions: # if "yes", we just skip part 1
            opposite_dir = {"up":"down","right":"left","down":"up","left":"right"}
            if directions[1]: # Autrement dit != None
                if directions[0] == opposite_dir[self.cur_dir]:
                    temp = directions[0]
                    directions = (directions[1], temp)
                # Sinon ne rien faire: la direction prioritaire est déjà la première

            else: # The only direction given needs to go back
                if self.cur_dir == "up" or self.cur_dir == "down":
                    directions = ("right","left")
                else:
                    directions = ("up","down")


    def get_move(self):
        """
        This method is regularly called by the client to get the next direction of the train.
        """
        self.main_path()
        
        
        moves = [Move.UP, Move.DOWN, Move.LEFT, Move.RIGHT]
        return Move.turn_left(self.cur_dir)
        
